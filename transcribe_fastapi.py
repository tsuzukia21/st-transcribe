import asyncio  
from faster_whisper import WhisperModel  
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState
import websockets
import logging

# 秒数を「○分○秒」形式に変換する関数
def convert_seconds(seconds):  
    minutes = seconds // 60  # 分を計算（整数除算）
    remaining_seconds = seconds % 60  # 残りの秒数
    return f"{int(minutes)}分{int(remaining_seconds)}秒"  

# WebSocketメッセージ送信のヘルパー関数
async def send_websocket_message(websocket, message, session_id):
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(message)
            return True
    except (WebSocketDisconnect, websockets.exceptions.ConnectionClosedOK, RuntimeError) as e:
        logging.info(f"WebSocket connection issue for session {session_id}")
        return False

# 音声ファイルを文字起こしする非同期関数
async def transcribe(audio_file, websocket: WebSocket, session_id: int, should_stop):  
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")

    try:
        # モデルによる文字起こし処理（CPUバウンドな処理なのでto_threadで実行）
        segments, info = await asyncio.to_thread(  
            model.transcribe,  
            audio_file,  
            language="ja",  # 日本語を指定
            beam_size=5,    # ビームサイズ（精度向上のため）
            vad_filter=True, # 声の検出フィルターを有効化
            without_timestamps=True,  # タイムスタンプなし
        )  
    except Exception as e:
        logging.error(f"Error during model.transcribe: {e}")
        # エラーが発生した場合もクライアントに通知
        await send_websocket_message(
            websocket, 
            {"type": "error", "message": "Transcription failed during processing.", "done": True},
            session_id
        )
        return

    # 音声ファイルの長さを取得
    audio_length = info.duration

    # 文字起こし情報をクライアントに送信
    message_sent = await send_websocket_message(
        websocket,
        {  
            "type": "info",  
            "language": info.language,  
            "language_probability": info.language_probability,  
            "length": convert_seconds(audio_length),  
            "done": False  
        },
        session_id
    )
    
    if not message_sent:
        return  # 接続が切れていたら終了

    # 文字起こし結果を格納する変数
    final_text = ""  
    
    # 各セグメント（文章単位の音声）を処理
    for segment in segments:  
        # 停止要求があった場合は処理を中断
        if should_stop():  
            logging.info(f"Transcription stopped by request")
            await send_websocket_message(
                websocket,
                {"type": "stopped", "done": True},
                session_id
            )
            return

        # 文字起こし結果を累積
        final_text += segment.text  

        # タイムライン形式のテキスト（開始時間→終了時間 + テキスト）
        time_line = f"[{convert_seconds(segment.start)} -> {convert_seconds(segment.end)}] {segment.text}"  
        
        # 進捗率の計算
        progress = 0
        if audio_length > 0:
            progress = int(segment.end / audio_length * 100)

        # セグメント結果をクライアントに送信
        message_sent = await send_websocket_message(
            websocket,
            {  
                "type": "segment",  
                "data": {  
                    "time_line": time_line,  
                    "text": segment.text     
                },  
                "progress": progress,  
                "done": False  
            },
            session_id
        )
        
        if not message_sent:
            return  # 接続が切れていたら終了

        # 非同期処理の機会を与える
        await asyncio.sleep(0)

    # 最終的な文字起こし結果をクライアントに送信
    await send_websocket_message(
        websocket,
        {  
            "type": "final",  
            "data": {  
                "result": final_text  
            },  
            "done": True 
        },
        session_id
    )
    logging.info("Transcription completed successfully")