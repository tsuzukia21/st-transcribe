import streamlit as st  
import json  
import asyncio  
import os  
import websockets  
import base64  
import threading  
import requests
from st_txt_copybutton import txt_copy
import tempfile

# WebSocket接続を管理するクラス
class WebSocketManager:
    def __init__(self):
        self.websocket = None
        self.lock = threading.Lock()
    
    async def connect(self):
        uri = "ws://localhost:5001/ws"
        try:
            self.websocket = await websockets.connect(uri, ping_interval=20, ping_timeout=120)
            return self.websocket
        except Exception as e:
            st.error(f"サーバー接続エラー: {e}")
            return None
    
    async def send(self, message):
        if not self.websocket:
            return False
        try:
            await asyncio.wait_for(self.websocket.send(message), timeout=300)
            return True
        except (asyncio.TimeoutError, Exception) as e:
            st.error(f"送信エラー: {e}")
            return False
    
    async def close(self):
        if self.websocket:
            try:
                await self.websocket.send(json.dumps({"type": "stop"}))
                await asyncio.sleep(2)
                await self.websocket.close()
            except Exception as e:
                pass
            finally:
                self.websocket = None

# WebSocketマネージャーのインスタンスを作成
ws_manager = WebSocketManager()

# 文字起こしリクエストをサーバーに送信する非同期関数
async def send_transcribe_request(websocket, model, button_save_audio, audio_file_path):  
    # 音声ファイルをバイナリで読み込み
    with open(audio_file_path, "rb") as f:  
        audio_file = f.read()  

    # バイナリデータをBase64エンコード
    audio_base64 = base64.b64encode(audio_file).decode('utf-8')  

    # リクエストメッセージを作成
    message = json.dumps({
        "type": "transcribe",
        "audio": audio_base64,
        "model": model,
        "save_audio": button_save_audio,
        "file_name": audio_file_path
    })

    return await ws_manager.send(message)

# 文字起こし結果を受信して表示する非同期関数
async def receive_transcription_results(websocket):
    # Streamlitのステータス表示を開始
    with st.status("**文字起こし実行中...**", state="running", expanded=True) as status:
        transcribe_result = st.empty()  # 文字起こし結果を表示するための空のコンテナ
        try:
            # WebSocketからメッセージを非同期で受信し続ける
            async for message in websocket:  
                # 停止イベントがセットされていれば処理を中断
                if st.session_state.stop_event.is_set():  
                    break  

                # JSONメッセージをパース
                data = json.loads(message)  
                if "error" in data:  
                    st.error(f"エラー: {data['error']}")  
                elif "done" in data and data["done"]:  
                    # 処理完了の通知を受けたら完了イベントをセット
                    st.session_state.done_event.set()  
                    break  
                else:  
                    # テキストデータがあれば表示
                    if 'text' in data.get('data', {}):  
                        text = data['data']['text']  
                        timeline = data['data']['time_line']  
                        transcribe_result.markdown(timeline)  # タイムラインを表示
                        st.session_state.full_text_transcribe += text  # 全文を累積
                        percent_complete = data['progress']  # 進捗率
                        st.session_state.progress_bar.progress(int(percent_complete), text=st.session_state.progress_text)  
            transcribe_result.empty()  # 表示をクリア
            status.update(label="**文字起こし完了!**", state="complete", expanded=False)
        except websockets.exceptions.ConnectionClosed:  
            st.error("サーバーとの接続が切断されました")  

# 文字起こし処理のメイン非同期関数
async def transcribe(model, button_save_audio, audio_file_path):  
    # 進捗バーを初期化
    st.session_state.progress_text = "処理中です。お待ちください。"  
    st.session_state.progress_bar = st.progress(0, text=st.session_state.progress_text)  

    try:  
        # サーバーに接続
        websocket = await ws_manager.connect()  
        if websocket:  
            # 文字起こしリクエストを送信し、結果を受信
            if await send_transcribe_request(websocket, model, button_save_audio, audio_file_path):  
                await receive_transcription_results(websocket)  
            else:  
                st.error("リクエスト送信に失敗しました")  
        else:  
            st.error("サーバーとの接続に失敗しました")  
    except Exception as e:  
        st.error(f"エラー: {e}")  
    finally:  
        # 後処理
        await ws_manager.close()  
        st.session_state.stop_event.clear()  
        st.session_state.done_event.clear()  

    # 進捗バーを消去
    if 'progress_bar' in st.session_state:
        st.session_state.progress_bar.empty()  

# 文字起こし処理を実行する関数
def process_transcription(model, button_save_audio, audio_file_path):
    asyncio.run(transcribe(model, button_save_audio, audio_file_path))

# セッション状態の初期化
if 'full_text_transcribe' not in st.session_state:  
    st.session_state.full_text_transcribe = ""  # 文字起こし結果の全文
if 'done_event' not in st.session_state:  
    st.session_state.done_event = asyncio.Event()  # 文字起こし完了イベント
if 'stop_event' not in st.session_state:  
    st.session_state.stop_event = asyncio.Event()  # 文字起こし停止イベント
if 'server_status' not in st.session_state:  
    st.session_state.server_status = False  # サーバー接続状態

# アプリのタイトル
st.title("音声文字起こし")
st.write('**Whisperを利用して音声データを文字起こしすることが出来ます。**')

# サーバー接続状態のチェック
if st.session_state.server_status == "":
    with st.spinner("サーバーのチェック中..."):  
        try:
            # サーバーが起動しているか確認
            requests.get("http://localhost:5001/")
            st.session_state.server_status = True
        except requests.ConnectionError:
            st.session_state.server_status = False

# サーバーが起動していない場合はエラーを表示して終了
if st.session_state.server_status == False:
    st.error('サーバーが立ち上がっていません。', icon=":material/error:")
    st.stop()

# サーバーが起動している場合はUIを表示
if st.session_state.server_status == True:
    # モデル選択ラジオボタン
    model = st.radio("model", ["汎用モデル", "チューニングモデル"])
    # 音声ファイルアップローダー
    uploaded_file = st.file_uploader("音声ファイルをアップロードしてください", type=["mp3", "wav", "m4a", "mp4"], key="audio_file_trancribe")

    if uploaded_file is not None:
        # アップロードされたファイルを一時ファイルとして保存
        temp_dir = tempfile.gettempdir()
        audio_file_path = os.path.join(temp_dir, uploaded_file.name)
        
        with open(audio_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # 音声ファイルのフィードバックオプション
        if button_save_audio := st.toggle("学習用の為音声ファイルをフィードバックする", key="button_save_audio",
                                            help="音声文字起こしモデルを改善するために、音声ファイルを集めています。音声ファイルを学習データとして利用させていただきます。"):
            st.subheader("ご協力ありがとうございます")
            st.balloons()
        
        # 文字起こし開始・停止ボタン
        col1, col2 = st.columns(2)  
        with col1:  
            trans_start = st.button("文字起こしを開始する", type="primary")  
        with col2:  
            trans_stop = st.button("文字起こしを停止する")  

        # 文字起こし開始ボタンが押された場合
        if trans_start:  
            st.session_state.stop_event.clear()  
            st.session_state.done_event.clear()  
            st.session_state.full_text_transcribe = ""  
            process_transcription(model, button_save_audio, audio_file_path)  

        # 文字起こし停止ボタンが押された場合
        if trans_stop:  
            st.session_state.stop_event.set()  
            st.rerun()  # Streamlitを再実行して状態を更新
            
    # 文字起こし結果がある場合に表示
    if st.session_state.full_text_transcribe:
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            # コピーボタン
            copy_button = txt_copy(label="文字起こし結果をコピーする", text_to_copy=st.session_state.full_text_transcribe.replace("\\n", "\n"), key="text_clipboard")
            if copy_button:
                st.toast("コピーしました！")
        with col2:
            # ダウンロードボタン
            audio_file_name = os.path.basename(audio_file_path).split(".")[0]
            st.download_button(label="文字起こし結果をダウンロードする", data=st.session_state.full_text_transcribe, file_name=f"{audio_file_name}.txt", mime="text/plain")
        # 文字起こし結果の表示
        st.write("\n**文字起こし結果**")
        st.write(st.session_state.full_text_transcribe)  