from flask import jsonify
from faster_whisper import WhisperModel

# 秒を「〇分〇秒」の形式に変換する関数
def convert_seconds(seconds):
    minutes = seconds // 60  # 分を計算（整数除算）
    remaining_seconds = seconds % 60  # 残りの秒を計算
    return f"{int(minutes)}分{int(remaining_seconds)}秒"

# 音声ファイルを文字起こしする関数
def transcribe(audio_file):
    # Whisperモデル（large-v3）をGPUで初期化
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    
    # 音声ファイルの文字起こしを実行
    segments, info = model.transcribe(audio_file,
                                      language = "ja",  # 日本語を指定
                                      beam_size=5,  # ビームサーチの幅（精度向上のため）
                                      vad_filter=True,  # 音声区間検出フィルターを有効化
                                      without_timestamps=True,  # タイムスタンプなしの出力を無効化
                                      prompt_reset_on_temperature=0,  # プロンプトリセットの温度閾値
                                      # initial_prompt=""  # 初期プロンプト（今回は未使用）
                                      )

    # 結果を格納する変数を初期化
    full_text=""  # 全文テキスト
    time_line=""  # タイムスタンプ付きテキスト
    
    # 各セグメント（文章）ごとに処理
    for segment in segments:
        # タイムスタンプ付きのテキストを生成（開始時間 -> 終了時間の形式）
        time_line+="[%s -> %s] %s" % (convert_seconds(segment.start), convert_seconds(segment.end), segment.text)+"  \n"
        # 全文テキストに追加
        full_text+=segment.text+"\n"

    # 結果をJSON形式で返すためのデータ作成
    result = {
        "language": info.language,  # 検出された言語
        "language_probability": info.language_probability,  # 言語検出の確信度
        "time_line":time_line,  # タイムスタンプ付きテキスト
        "full_text":full_text  # 全文テキスト
    }

    # JSON形式で結果を返す
    return jsonify(result)
