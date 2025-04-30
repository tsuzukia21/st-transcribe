from flask import Flask, request
import os
import logging
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)
from transcribe_flask import transcribe

# 文字起こしAPI（POSTリクエスト用）のエンドポイント
@app.route('/transcribe_server', methods=['POST'])
def transcribe_server():
    try:
        # リクエストからデータを取得
        audio_file = request.files['audio']  # 音声ファイル
        model = request.form['model']  # 使用するモデル
        save_audio = request.form['save_audio']  # 音声保存フラグ
        file_name = request.form['file_name']  # ファイル名
        
        # 音声ファイルを一時的に保存
        audio_file.save(file_name)
        
        # 学習用に音声を保存する場合の処理
        if save_audio == "True":  
            with open(file_name, 'rb') as f_src:  # 元ファイルを読み込み
                destination_path = "path_tp_save"  # 保存先のパス
                with open(destination_path, 'wb') as f_dst:  # 保存先ファイルに書き込み
                    f_dst.write(f_src.read())
        
        # 汎用モデルの場合の処理
        if model == "汎用モデル":
            result = transcribe(audio_file=file_name)  # 文字起こし実行

        # 一時ファイルを削除
        os.remove(file_name)
        return result  # 結果を返す

    except Exception as e:
        return str(e), 500  # エラーが発生した場合は500エラーを返す

# メインプログラム（直接実行された場合）
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)  # サーバーを起動（すべてのインターフェースでリッスン）