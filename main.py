# app.py
from flask import Flask, request, jsonify, render_template
import json
import math
import statistics

app = Flask(__name__)


# ─── Scoring Engine ────────────────────────────────────────────────────────────

def score_behavior(data: dict) -> dict:
    """
    Returns a score from 0-100. Higher = more likely a bot.
    Each check contributes penalty points.
    """
    score = 0
    flags = []

    mouse_moves = data.get("mouseMoves", [])
    key_intervals = data.get("keyIntervals", [])
    click_positions = data.get("clickPositions", [])
    focus_time = data.get("formFocusTime")
    submit_time = data.get("formSubmitTime")

    # ── 1. Mouse movement checks ──────────────────────────────────────────────

    if len(mouse_moves) == 0:
        score += 30
        flags.append("no_mouse_movement")

    elif len(mouse_moves) >= 3:
        # Check if movement is suspiciously linear (bots often move in straight lines)
        linearity = check_linearity(mouse_moves)
        if linearity > 0.98:
            score += 20
            flags.append("linear_mouse_movement")

        # Check if movement speed is unnaturally constant
        speeds = compute_speeds(mouse_moves)
        if speeds and coefficient_of_variation(speeds) < 0.05:
            score += 15
            flags.append("constant_mouse_speed")

    # 2. Keystroke timing checks

    if len(key_intervals) == 0:
        score += 20
        flags.append("no_keystrokes")
    
    elif len(key_intervals) >= 3:
        avg_interval = statistics.mean(key_intervals)
        cv = coefficient_of_variation(key_intervals)

        if cv < 0.1:
            score += 25
            flags.append("uniform_typing_speed")
        
        if avg_interval < 20:  # Extremely fast typing
            score += 20
            flags.append("superhuman_typing_speed")

    # 3. Time-on-form checks

    if focus_time and submit_time:
        time_on_form = submit_time - focus_time
        if time_on_form < 2000:  # Less than 2 seconds on form
            score += 25
            flags.append("instant_submission")
        elif time_on_form > 3000:  # More than 5 minutes on form
            score += 10
            flags.append("very_fast_submission")
    else:
        score += 15
        flags.append("missing_timing_data")
    
    # 4. Click behavior checks

    if len(click_positions) == 0:
        score += 10
        flags.append("no_clicks_recorded")
    
    score = min(score, 100)

    return {"score": score, "flags": flags}

# Math Helpers

def check_linearity(points: list) -> float:
    if len(points) < 3:
        return 0.0
    xs = [p['x'] for p in points]
    ys = [p['y'] for p in points]
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    demon_x = math.sqrt(sum((x - mean_x)**2 for x in xs))
    demon_y = math.sqrt(sum((y - mean_y)**2 for y in ys))
    if demon_x == 0 or demon_y == 0:
        return 1.0
    return abs(numerator / (demon_x * demon_y))

def compute_speeds(points: list) -> list:
    speeds = []
    for i in range(1, len(points)):
        dx = points[i]["x"] - points[i-1]["x"]
        dy = points[i]["y"] - points[i-1]["y"]
        dt = points[i]["t"] - points[i-1]["t"]
        if dt > 0:
            speed = math.sqrt(dx**2 + dy**2) / dt
            speeds.append(speed)
    return speeds

def coefficient_of_variation(data: list) -> float:
    if len(data) < 2:
        return 0.0
    mean = statistics.mean(data)
    if mean == 0:
        return 0.0
    return statistics.stdev(data) / mean

# Routes

@app.route("/")
def index():
    return render_template("login.html")

@app.route("/login", methods=["POST", "GET"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    raw_behavior = request.form.get("behavior_data", "{}")

    try:
        behavior_data = json.loads(raw_behavior)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid behavior data format", "blocked": True}), 400
    
    result = score_behavior(behavior_data)
    score = result["score"]
    flags = result["flags"]

    print(f"[BotDetector] User: {username}, Score: {score}, Flags: {flags}")

    # Decision threshold
    if score >= 60:
        return jsonify({
            "blocked": True,
            "reason": "Suspicious behavior detected",
            "score": score,
            "flags": flags
        }), 403
    elif score >= 35:
        return jsonify({
            "blocked": False,
            "warning": "Behavior is somewhat suspicious",
            "score": score,
            "flags": flags
        }), 200
    else:
        return jsonify({
            "blocked": False,
            "message": "Behavior looks normal",
            "score": score,
        }), 200

if __name__ == "__main__":
    app.run(debug=True)