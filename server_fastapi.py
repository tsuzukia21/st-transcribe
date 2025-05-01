from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from transcribe_fastapi import transcribe
import asyncio
import base64
import tempfile
from starlette.websockets import WebSocketState

# ロギングの設定（INFOレベルに設定）
logging.basicConfig(level=logging.INFO)
# FastAPIアプリケーションのインスタンス作成
app = FastAPI()

# CORSミドルウェアの追加（クロスオリジンリクエストを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべてのオリジンからのリクエストを許可
    allow_credentials=True,
    allow_methods=["*"],  # すべてのHTTPメソッドを許可
    allow_headers=["*"],  # すべてのHTTPヘッダーを許可
)

# セッション情報を管理する辞書
sessions = {}  # {session_id: {'stop': bool}}

# セッション終了時のクリーンアップ処理を行う関数
async def cleanup_session(session_id: int):
    logging.info('Client disconnected')
    if session_id in sessions:
        sessions.pop(session_id)  # セッションを削除

# WebSocketエンドポイント
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()  # WebSocket接続を受け入れる
    session_id = id(websocket)  # 一意のセッションIDを生成
    sessions[session_id] = {'stop': False}  # 新しいセッションを初期化
    logging.info('Client connected')

    try:
        while True:
            # クライアントからのJSONメッセージを待機
            data = await websocket.receive_json()
            if data.get("type") == "transcribe":
                # 文字起こしリクエストの処理
                await handle_transcribe(websocket, data, session_id)
            elif data.get("type") == "stop":
                # 停止リクエストの処理
                await handle_stop(websocket, session_id)
                break  # 停止リクエスト後にループを抜ける
    except WebSocketDisconnect:
        logging.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        # セッション終了時に必ずクリーンアップ処理を実行
        await cleanup_session(session_id)

# 停止リクエストを処理する関数
async def handle_stop(websocket: WebSocket, session_id: int):  
    logging.info(f"Stop requested for session {session_id}")  
    if session_id in sessions:  
        sessions[session_id]['stop'] = True  # 停止フラグをセット
        try:  
            # クライアントに停止確認を送信
            await websocket.send_json({'done': True, 'message': 'Transcription stopped'})  
        except (WebSocketDisconnect, RuntimeError) as e:  
            logging.info(f"Client disconnected while sending stop confirmation")  
        logging.info(f"Transcription stopped for session {session_id}")  
    else:  
        logging.info(f"No active transcription to stop for session {session_id}")

# 文字起こしリクエストを処理する関数
async def handle_transcribe(websocket: WebSocket, data: dict, session_id: int):
    temp_file_path = None
    try:
        # クライアントから送信されたデータを取得
        audio_base64 = data['audio']  # Base64エンコードされた音声データ
        model = data['model']  # 使用するモデル
        save_audio = data['save_audio']  # 音声を保存するかどうか
        file_name = data['file_name']  # ファイル名
        sessions[session_id]['stop'] = False  # 停止フラグを初期化

        # Base64デコードして音声データを取得
        audio_file = base64.b64decode(audio_base64)

        # 一時ファイルを作成して音声データを保存
        temp_dir = tempfile.gettempdir()  # 一時ディレクトリを取得
        temp_file_path = os.path.join(temp_dir, os.path.basename(file_name))
        with open(temp_file_path, 'wb') as f:
            f.write(audio_file)

        logging.info(f"Saved audio file temporarily")

        # フィードバック用に音声を保存するオプションが有効な場合
        if save_audio:
            destination_path = "path_to_save"  # 保存先のパス
            with open(destination_path, 'wb') as f_dst:
                f_dst.write(audio_file)
            logging.info(f"Saved audio file for feedback")

        # 文字起こし処理の実行（汎用モデルの場合）
        if model == "汎用モデル":
            await transcribe(temp_file_path, websocket, session_id, lambda: sessions[session_id]['stop'])

    except asyncio.CancelledError:
        logging.info(f"Transcription cancelled for session {session_id}")
    except WebSocketDisconnect:
        logging.info(f"WebSocket disconnected during transcription for session {session_id}")
    except Exception as e:
        logging.error(f"Error in handle_transcribe: {e}", exc_info=True)
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({"error": str(e), "done": True})
        except:
            pass
    finally:
        # 一時ファイルの削除
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logging.info(f"Temporary file removed")
        try:
            # 処理完了をクライアントに通知
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({"done": True})
        except:
            logging.info(f"Client disconnected before sending final message")

# サーバー起動のためのエントリーポイント
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",  # すべてのネットワークインターフェースでリッスン
        port=5001,  # ポート番号
        ws_max_size=5 * 1024 * 1024 * 1024,  # WebSocketメッセージの最大サイズ（5GB）
        timeout_keep_alive=500,  # キープアライブタイムアウト
    )