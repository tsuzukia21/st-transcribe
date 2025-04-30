import streamlit as st
import requests
import time

# 秒を「〇分〇秒」の形式に変換する関数
def convert_seconds(seconds):
    minutes = seconds // 60  # 分を計算（整数除算）
    remaining_seconds = seconds % 60  # 残りの秒を計算
    return f"{int(minutes)}分{int(remaining_seconds)}秒"

# アプリケーションのタイトルと説明を設定
st.title("音声文字起こし")
st.write('**Whisperを利用して音声データを文字起こしすることが出来ます。**')

# サーバーのURL設定
server_url = "http://localhost:5000/"

# サーバーに接続できるか確認
with st.spinner("サーバーのチェック中..."):  
    try:
        requests.get(server_url)  # サーバーへのGETリクエスト
    except requests.ConnectionError:
        st.error('サーバーが立ち上がっていません。', icon="🚨")  # エラーメッセージを表示
        st.stop()  # アプリを停止

# モデル選択のラジオボタン
model = st.radio("model",["汎用モデル","チューニングモデル"])

# 音声ファイルのアップロード機能
audio_file = st.file_uploader("音声ファイルをアップロードしてください", type=["mp3", "wav", "m4a", "mp4"],key="audio_file_trancribe")

# ファイルがアップロードされた場合の処理
if audio_file:
    # 出力ファイル名を設定
    st.session_state.transcribe_file_name = "文字起こし結果_"+audio_file.name.replace(".mp4","").replace(".mp3","").replace(".wav","").replace(".m4a","")+".txt"
    
    # 学習用データ提供のトグルボタン
    if button_save_audio := st.toggle("学習用の為音声ファイルをフィードバックする",key="button_save_audio",
                                        help="音声文字起こしモデルを改善するために、音声ファイルを集めています。音声ファイルを学習データとして利用させていただきます。"):
        st.subheader("ご協力ありがとうございます🤗")
        st.balloons()  # 風船エフェクトを表示
    
    # 文字起こし開始ボタン
    button_trans_start = st.button("文字起こしを開始する",type="primary")
    if button_trans_start:
        start_time = time.time()  # 処理開始時間を記録
        with st.spinner("**文字起こしを実行中...**"):
            try:
                # サーバーにデータを送信して文字起こし実行をリクエスト
                response = requests.post(
                    server_url+"transcribe_server",
                    files={"audio": audio_file.getvalue()},  # 音声ファイルデータ
                    data={"model": model,"save_audio":button_save_audio,"file_name":audio_file.name},  # 追加データ
                )

                if response.status_code == 200:  # 成功の場合
                    end_time = time.time()  # 処理終了時間を記録
                    st.session_state.execution_time = end_time - start_time  # 実行時間を計算
                    st.session_state.transcribe_data = response.json()  # 結果データを保存
                else:
                    st.write("Error: ", response.text)  # エラーメッセージを表示
            except requests.ConnectionError:
                st.error('サーバーとの接続が解除されました。', icon="🚨")
                st.stop()

# 文字起こし結果の表示
if "transcribe_data" in st.session_state:
    st.write("実行時間：", convert_seconds(st.session_state.execution_time))  # 実行時間を表示
    probability = round(float(st.session_state.transcribe_data['language_probability']) * 100, 1)  # 言語検出の確信度を計算
    st.write(f"検出言語: {st.session_state.transcribe_data['language']} 信用度 {probability}%")  # 検出言語と確信度を表示
    
    # 文字起こし結果のダウンロードボタン
    st.download_button(label="文字起こし結果をダウンロードする",data=st.session_state.transcribe_data["full_text"],file_name=st.session_state.transcribe_file_name,icon=":material/download:")
    
    # 文字起こし結果の表示
    st.markdown("**文字起こし結果**")
    st.markdown(st.session_state.transcribe_data["time_line"], unsafe_allow_html=True)  # タイムスタンプ付きの文字起こし結果を表示
