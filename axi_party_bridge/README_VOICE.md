# AXI Voice Loop MVP

## 起動方法

マイク入力:

```bash
cd ~/AXI/axi_party_bridge
./start_voice_loop.sh
```

標準入力フォールバック:

```bash
cd ~/AXI/axi_party_bridge
python3 rodorin_voice_loop.py --stdin
```

## 動作

- 音声認識または標準入力の文章を `speaker=rodorin` として Party Bus に追記します。
- 短すぎる発言は捨てます。
- 同じ文の連投を防ぎます。
- 無音時は何もしません。

出力形式:

```json
{"speaker":"rodorin","text":"今の危なかったね","ts":1234567890.0}
```
