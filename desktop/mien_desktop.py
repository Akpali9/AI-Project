"""Mien Desktop: control your computer with facial gestures.

Run:  python mien_desktop.py        Keys in the window: c = recalibrate, p = pause, q = quit
Rules live in rules.json (see README.md). Video never leaves your machine.
"""
import json, math, os, subprocess, time, urllib.request, webbrowser
import cv2
import mediapipe as mp
import pyautogui
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "face_landmarker.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_landmarker/"
             "face_landmarker/float16/1/face_landmarker.task")
RULES = os.path.join(HERE, "rules.json")
AMBER, GREY = (71, 181, 255), (120, 130, 140)  # BGR

GESTURES = {
    "smile": "Smile", "mouth_open": "Open mouth", "brows": "Raise eyebrows",
    "blink": "Long blink", "wink_l": "Wink left eye", "wink_r": "Wink right eye",
    "pucker": "Pucker lips", "turn_l": "Turn head left", "turn_r": "Turn head right",
    "look_up": "Tilt head up", "look_down": "Tilt head down",
}

clamp = lambda v, a=0.0, b=1.0: max(a, min(b, v))


def feats(l, bs, w, h):
    """Raw measurements from landmarks + blendshapes (same maths as the web app)."""
    B = lambda n: bs.get(n, 0.0)
    d = lambda i, j: math.hypot((l[i].x - l[j].x) * w, (l[i].y - l[j].y) * h)
    ear = lambda a, b, c, e, f, g: (d(b, g) + d(c, f)) / (2 * d(a, e))
    eye_y = (l[33].y + l[263].y) / 2
    return dict(
        smile=(B("mouthSmileLeft") + B("mouthSmileRight")) / 2,
        jaw=B("jawOpen"),
        brow=(B("browInnerUp") + (B("browOuterUpLeft") + B("browOuterUpRight")) / 2) / 2,
        blink=min(B("eyeBlinkLeft"), B("eyeBlinkRight")),
        pucker=B("mouthPucker"),
        earR=ear(33, 160, 158, 133, 153, 144),
        earL=ear(362, 385, 387, 263, 373, 380),
        yaw=(l[1].x - (l[234].x + l[454].x) / 2) / abs(l[454].x - l[234].x),
        pitch=(l[1].y - eye_y) / (l[152].y - eye_y),
    )


def strengths(F, base):
    x = lambda k: F[k] - base.get(k, 0.0)
    cl = clamp((base["earL"] - F["earL"]) / (base["earL"] * 0.7))
    cr = clamp((base["earR"] - F["earR"]) / (base["earR"] * 0.7))
    return dict(
        smile=clamp(x("smile") / 0.55), mouth_open=clamp(x("jaw") / 0.45),
        brows=clamp(x("brow") / 0.4), blink=clamp(x("blink") / 0.6),
        pucker=clamp(x("pucker") / 0.5),
        wink_l=clamp(cl - 0.7 * cr), wink_r=clamp(cr - 0.7 * cl),
        turn_l=clamp(x("yaw") / 0.22), turn_r=clamp(-x("yaw") / 0.22),
        look_up=clamp(-x("pitch") / 0.15), look_down=clamp(x("pitch") / 0.15),
    )


def do_action(action, param=""):
    """Run one action. Returns a short description for the on-screen log."""
    p = (param or "").replace("{time}", time.strftime("%H:%M:%S")).replace("{date}", time.strftime("%Y-%m-%d"))
    if action == "scroll_up":
        pyautogui.scroll(120)
    elif action == "scroll_down":
        pyautogui.scroll(-120)
    elif action == "key":            # "ctrl+tab", "left", "playpause", "volumeup" ...
        pyautogui.hotkey(*p.split("+"))
    elif action == "type_text":
        pyautogui.write(p.replace("\\n", "\n"), interval=0.01)
    elif action == "click":
        pyautogui.click()
    elif action == "right_click":
        pyautogui.click(button="right")
    elif action == "open_url":
        webbrowser.open(p if p.startswith("http") else "https://" + p)
    elif action == "screenshot":
        pyautogui.screenshot(os.path.join(HERE, f"mien-{int(time.time())}.png"))
    elif action == "command":         # runs a shell command you wrote in rules.json
        subprocess.Popen(p, shell=True)
    return action + (f": {p}" if p else "")


def ensure_model():
    if not os.path.exists(MODEL):
        print("Downloading face model (one time, ~4 MB)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL)


def hud(img, sm, status, note):
    cv2.putText(img, status, (14, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, AMBER, 2, cv2.LINE_AA)
    for i, (g, label) in enumerate(GESTURES.items()):
        y = 56 + i * 24
        cv2.putText(img, label, (14, y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (235, 235, 235), 1, cv2.LINE_AA)
        cv2.rectangle(img, (150, y), (270, y + 12), (60, 66, 72), -1)
        cv2.rectangle(img, (150, y), (150 + int(120 * sm[g]), y + 12), AMBER if sm[g] >= 0.6 else GREY, -1)
    if note:
        cv2.putText(img, note, (14, img.shape[0] - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, AMBER, 2, cv2.LINE_AA)
    cv2.putText(img, "c recalibrate   p pause   q quit", (14, img.shape[0] - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)


def main():
    ensure_model()
    rules = json.load(open(RULES, encoding="utf-8"))
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise SystemExit("No camera found. Connect one, or allow camera access for your terminal.")
    det = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=MODEL),
        running_mode=vision.RunningMode.VIDEO, num_faces=1, output_face_blendshapes=True))

    base = dict(earL=0.27, earR=0.27, pitch=0.55, yaw=0.0)
    cal, calibrated, paused = None, False, False
    sm = {g: 0.0 for g in GESTURES}
    state, note, note_until = {}, "", 0
    t0 = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int((time.time() - t0) * 1000))
        now = time.time() * 1000
        face = bool(res.face_landmarks)

        if face:
            bs = {c.category_name: c.score for c in res.face_blendshapes[0]}
            F = feats(res.face_landmarks[0], bs, w, h)
            if not calibrated:
                cal = cal or dict(t=now, n=0, sum={})
                for k, v in F.items():
                    cal["sum"][k] = cal["sum"].get(k, 0.0) + v
                cal["n"] += 1
                if now - cal["t"] > 2000:
                    base = {k: v / cal["n"] for k, v in cal["sum"].items()}
                    calibrated, cal = True, None
            else:
                s = strengths(F, base)
                for g in sm:
                    sm[g] += (s[g] - sm[g]) * 0.5
        else:
            for g in sm:
                sm[g] *= 0.6

        if calibrated:
            for i, r in enumerate(rules):
                if not r.get("on", True):
                    continue
                st = state.setdefault(i, dict(since=None, armed=True, last=0))
                if paused and r["action"] != "toggle_pause":
                    st["since"] = None
                    continue
                v, th = sm.get(r["gesture"], 0.0), r.get("threshold", 0.6)
                if v >= th:
                    st["since"] = st["since"] or now
                    if now - st["since"] >= r.get("hold_ms", 300) and st["armed"]:
                        fire = False
                        if r.get("repeat"):
                            fire = now - st["last"] >= r.get("repeat_ms", 80)
                        elif now - st["last"] >= r.get("cooldown_ms", 800):
                            fire, st["armed"] = True, False
                        if fire:
                            st["last"] = now
                            try:
                                if r["action"] == "toggle_pause":
                                    paused = not paused
                                    msg = "paused" if paused else "resumed"
                                else:
                                    msg = do_action(r["action"], r.get("param", ""))
                            except Exception as e:  # keep running if one action fails
                                msg = f"failed ({e})"
                            if not r.get("repeat"):
                                note, note_until = f"{GESTURES.get(r['gesture'], r['gesture'])}: {msg}", now + 1200
                elif v < th * 0.6:
                    st["since"], st["armed"] = None, True

        status = ("Calibrating: relax your face" if not calibrated else "Paused" if paused
                  else "Live" if face else "No face in view")
        view = cv2.flip(frame, 1)
        hud(view, sm, status, note if now < note_until else "")
        cv2.imshow("Mien", view)
        k = cv2.waitKey(1) & 255
        if k == ord("q") or cv2.getWindowProperty("Mien", cv2.WND_PROP_VISIBLE) < 1:
            break
        if k == ord("p"):
            paused = not paused
        if k == ord("c"):
            calibrated, cal = False, None

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
