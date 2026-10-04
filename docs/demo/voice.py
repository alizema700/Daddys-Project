#!/usr/bin/env python3
"""Add a voice-over to prob_live_demo.mp4.

  python docs/demo/voice.py --engine say --voice "Ava (Premium)"         # macOS, no key needed
  python docs/demo/voice.py --engine openai --voice onyx                 # needs OPENAI_API_KEY
  python docs/demo/voice.py --engine elevenlabs --voice <voice_id>       # needs ELEVENLABS_API_KEY
  python docs/demo/voice.py --list-voices --engine say                   # show available voices

Options: --rate 1.0 (speed), --style "..." (OpenAI tone instruction), --music file.mp3 (optional bed, ducked).
Text and timing live in narration.json. Each line starts at its 'at'; a line that would run into the next one
is sped up (max 1.25x) and reported. Output: prob_live_demo_voice.mp4 next to the video. Needs ffmpeg.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def tts(engine, text, voice, out, a):
    if engine == "say":
        aiff = out + ".aiff"
        cmd = ["say", "-o", aiff]
        if voice: cmd += ["-v", voice]
        cmd += ["-r", str(int(175 * a.rate)), text]
        run(cmd); run(["ffmpeg", "-y", "-i", aiff, "-ar", "48000", "-ac", "1", out]); os.remove(aiff)
    elif engine == "openai":
        body = {"model": "gpt-4o-mini-tts", "voice": voice or "onyx", "input": text, "format": "wav", "speed": a.rate,
                "instructions": a.style}
        req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
                                              "Content-Type": "application/json"})
        raw = out + ".raw.wav"
        open(raw, "wb").write(urllib.request.urlopen(req).read())
        run(["ffmpeg", "-y", "-i", raw, "-ar", "48000", "-ac", "1", out]); os.remove(raw)
    elif engine == "elevenlabs":
        vid = voice or "JBFqnCBsd6RMkjVDRZzb"
        body = {"text": text, "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.25, "speed": a.rate}}
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_128",
                                     data=json.dumps(body).encode(),
                                     headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
        mp3 = out + ".mp3"
        open(mp3, "wb").write(urllib.request.urlopen(req).read())
        run(["ffmpeg", "-y", "-i", mp3, "-ar", "48000", "-ac", "1", out]); os.remove(mp3)
    elif engine == "test":  # pipeline check without any voice: a soft tone as long as the line would be spoken
        secs = max(0.4, len(text.split()) / 2.6)
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=f=220:d={secs}", "-af", "volume=0.15", "-ar", "48000", "-ac", "1", out])
    else:
        sys.exit("unknown engine")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--engine", choices=["say", "openai", "elevenlabs", "test"], default="say")
    p.add_argument("--voice", default="")
    p.add_argument("--rate", type=float, default=1.0)
    p.add_argument("--style", default="Calm, precise keynote narrator. Slight tension on the reject and the surprise, warm on the ending.")
    p.add_argument("--music", default="")
    p.add_argument("--video", default=os.path.join(HERE, "prob_live_demo.mp4"))
    p.add_argument("--out", default=os.path.join(HERE, "prob_live_demo_voice.mp4"))
    p.add_argument("--list-voices", action="store_true")
    a = p.parse_args()
    if a.list_voices:
        if a.engine == "say": subprocess.run(["say", "-v", "?"])
        elif a.engine == "openai": print("alloy ash ballad coral echo fable nova onyx sage shimmer verse")
        else: print("Pick a voice id in the ElevenLabs voice library and pass it with --voice.")
        return
    if not shutil.which("ffmpeg"): sys.exit("ffmpeg is required")
    lines = json.load(open(os.path.join(HERE, "narration.json")))["lines"]
    total = duration(a.video)
    tmp = tempfile.mkdtemp()
    clips = []
    for i, ln in enumerate(lines):
        raw = os.path.join(tmp, f"l{i:02d}.wav")
        tts(a.engine, ln["text"], a.voice, raw, a)
        slot = (lines[i + 1]["at"] if i + 1 < len(lines) else total) - ln["at"] - 0.15
        d = duration(raw)
        if d > slot:
            f = min(1.25, d / slot)
            fit = os.path.join(tmp, f"f{i:02d}.wav")
            run(["ffmpeg", "-y", "-i", raw, "-af", f"atempo={f:.3f}", fit]); raw = fit
            note = f"sped up {f:.2f}x" + ("  (still too long: shorten the text)" if d / slot > 1.25 else "")
        else:
            note = "ok"
        print(f"{ln['at']:5.1f}s  {d:4.1f}s / slot {slot:4.1f}s  {note}  | {ln['text']}")
        clips.append((raw, ln["at"]))
    inputs, filt = [], []
    for k, (c, at) in enumerate(clips):
        inputs += ["-i", c]
        ms = int(at * 1000)
        filt.append(f"[{k + 1}:a]adelay={ms}|{ms}[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(len(clips)))
    filt.append(f"{mix}amix=inputs={len(clips)}:normalize=0,apad,atrim=0:{total}[vo]")
    last = "[vo]"
    if a.music:
        inputs += ["-stream_loop", "-1", "-i", a.music]
        m = len(clips) + 1
        filt.append(f"[{m}:a]volume=0.18,atrim=0:{total},afade=t=out:st={total - 2}:d=2[bg]")
        filt.append("[vo]asplit=2[vo1][vo2]")
        filt.append("[bg][vo1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[bgd]")
        filt.append("[bgd][vo2]amix=inputs=2:normalize=0[mx]")
        last = "[mx]"
    filt.append(f"{last}loudnorm=I=-16:TP=-1.5:LRA=11[out]")
    cmd = ["ffmpeg", "-y", "-i", a.video] + inputs + ["-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[out]",
                                                       "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", a.out]
    run(cmd)
    shutil.rmtree(tmp)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
