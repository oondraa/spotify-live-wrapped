import os
import sqlite3
from functools import wraps

import pandas as pd
from flask import Flask, render_template_string, session, redirect, url_for, request

from config import ADMIN_PASSWORD, ADMIN_USERNAME, DB_PATH, FLASK_SECRET_KEY, WEB_HOST, WEB_PORT

APP_TITLE = os.environ.get("APP_TITLE", "Spotify Live Wrapped")

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY or os.urandom(32)

NOT_CONFIGURED = not (ADMIN_USERNAME and ADMIN_PASSWORD and FLASK_SECRET_KEY)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if NOT_CONFIGURED:
            return render_template_string(SETUP_TEMPLATE)
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_data():
    conn = sqlite3.connect(DB_PATH)

    # 1. Datum spuštění
    start_date_query = pd.read_sql_query("SELECT MIN(played_at) as start FROM history", conn)
    start_date = start_date_query.iloc[0]['start'][:10] if not start_date_query.empty and start_date_query.iloc[0]['start'] else "N/A"

    # 2. Celkový čas (OPTIMALIZOVÁNO)
    total_ms_query = pd.read_sql_query("SELECT SUM(duration_ms) as total FROM history", conn)
    total_ms = total_ms_query.iloc[0]['total'] if not total_ms_query.empty and total_ms_query.iloc[0]['total'] else 0
    total_min = int((total_ms / (1000 * 60)) % 60)
    total_hours = int(total_ms / (1000 * 60 * 60))

    # 3. Počet přehraných skladeb
    total_plays_query = pd.read_sql_query("SELECT COUNT(*) as count FROM history", conn)
    total_plays = total_plays_query.iloc[0]['count'] if not total_plays_query.empty else 0

    # 4. Počet unikátních skladeb
    unique_tracks_query = pd.read_sql_query("SELECT COUNT(DISTINCT track_id) as count FROM history", conn)
    unique_tracks = unique_tracks_query.iloc[0]['count'] if not unique_tracks_query.empty else 0

    # 5. Top 10 Artistů (OPTIMALIZOVÁNO s LIMIT)
    top_artists = pd.read_sql_query("""
        SELECT artist_name, image_url, COUNT(*) as count
        FROM history
        GROUP BY artist_name
        ORDER BY count DESC
        LIMIT 10
    """, conn)

    # 6. Top 10 Skladeb (OPTIMALIZOVÁNO s LIMIT)
    top_tracks = pd.read_sql_query("""
        SELECT track_name, artist_name, image_url, COUNT(*) as count
        FROM history
        GROUP BY track_id
        ORDER BY count DESC
        LIMIT 10
    """, conn)

    # 7. Počet unikátních artistů
    unique_artists_query = pd.read_sql_query("SELECT COUNT(DISTINCT artist_id) as count FROM history", conn)
    unique_artists = unique_artists_query.iloc[0]['count'] if not unique_artists_query.empty else 0

    # 8. Počet unikátních alb
    unique_albums_query = pd.read_sql_query("SELECT COUNT(DISTINCT album_name) as count FROM history", conn)
    unique_albums = unique_albums_query.iloc[0]['count'] if not unique_albums_query.empty else 0

    # 9. Průměr skladeb za den (OPTIMALIZOVÁNO)
    days_tracking_query = pd.read_sql_query("""
        SELECT JULIANDAY(MAX(played_at)) - JULIANDAY(MIN(played_at)) + 1 as days
        FROM history
    """, conn)
    days_tracking = days_tracking_query.iloc[0]['days'] if not days_tracking_query.empty else 1
    avg_per_day = int(total_plays / days_tracking) if days_tracking > 0 else 0

    # 10. Top 10 alb (OPTIMALIZOVÁNO s LIMIT)
    top_albums = pd.read_sql_query("""
        SELECT album_name, artist_name, image_url, COUNT(*) as count
        FROM history
        GROUP BY album_name
        ORDER BY count DESC
        LIMIT 10
    """, conn)

    # 11. Poslední 24 hodin (OPTIMALIZOVÁNO - rychlý index na played_at)
    last_24h_query = pd.read_sql_query("""
        SELECT COUNT(*) as count
        FROM history
        WHERE datetime(played_at) >= datetime('now', '-1 day')
    """, conn)
    last_24h = last_24h_query.iloc[0]['count'] if not last_24h_query.empty else 0

    # 12. Tento týden (OPTIMALIZOVÁNO)
    last_7d_query = pd.read_sql_query("""
        SELECT COUNT(*) as count
        FROM history
        WHERE datetime(played_at) >= datetime('now', '-7 day')
    """, conn)
    last_7d = last_7d_query.iloc[0]['count'] if not last_7d_query.empty else 0

    # 13. Repeat rate (OPTIMALIZOVÁNO)
    repeat_rate = int((1 - (unique_tracks / total_plays)) * 100) if total_plays > 0 else 0

    # 14. Top den (OPTIMALIZOVÁNO s LIMIT 1)
    top_day = pd.read_sql_query("""
        SELECT DATE(played_at) as day, COUNT(*) as count
        FROM history
        GROUP BY day
        ORDER BY count DESC
        LIMIT 1
    """, conn)

    if not top_day.empty:
        top_day_date = top_day.iloc[0]['day']
        top_day_count = top_day.iloc[0]['count']
    else:
        top_day_date, top_day_count = "N/A", 0

    # 15. Den v týdnu statistika (OPTIMALIZOVÁNO)
    weekday_stats = pd.read_sql_query("""
        SELECT
            CASE CAST(strftime('%w', played_at) AS INTEGER)
                WHEN 0 THEN 'Neděle'
                WHEN 1 THEN 'Pondělí'
                WHEN 2 THEN 'Úterý'
                WHEN 3 THEN 'Středa'
                WHEN 4 THEN 'Čtvrtek'
                WHEN 5 THEN 'Pátek'
                WHEN 6 THEN 'Sobota'
            END as day_name,
            COUNT(*) as count
        FROM history
        GROUP BY strftime('%w', played_at)
        ORDER BY count DESC
        LIMIT 1
    """, conn)

    favorite_weekday = weekday_stats.iloc[0]['day_name'] if not weekday_stats.empty else "N/A"
    favorite_weekday_count = weekday_stats.iloc[0]['count'] if not weekday_stats.empty else 0

    # 16. Night owl score (OPTIMALIZOVÁNO)
    night_plays = pd.read_sql_query("""
        SELECT COUNT(*) as count
        FROM history
        WHERE CAST(strftime('%H', played_at) AS INTEGER) >= 22
           OR CAST(strftime('%H', played_at) AS INTEGER) < 6
    """, conn)
    night_count = night_plays.iloc[0]['count'] if not night_plays.empty else 0
    night_percentage = int((night_count / total_plays) * 100) if total_plays > 0 else 0

    # 17. Průměrná délka skladby
    avg_duration = pd.read_sql_query("SELECT AVG(duration_ms) as avg FROM history", conn)
    avg_ms = avg_duration.iloc[0]['avg'] if not avg_duration.empty else 0
    avg_min = int((avg_ms / (1000 * 60)) % 60)
    avg_sec = int((avg_ms / 1000) % 60)

    # 18. Top 3 hodiny (OPTIMALIZOVÁNO s LIMIT)
    hourly_stats = pd.read_sql_query("""
        SELECT
            CAST(strftime('%H', played_at) AS INTEGER) as hour,
            COUNT(*) as count
        FROM history
        GROUP BY hour
        ORDER BY count DESC
        LIMIT 3
    """, conn)

    # 19. Všechny hodiny pro graf (OPTIMALIZOVÁNO)
    hourly_chart = pd.read_sql_query("""
        SELECT
            CAST(strftime('%H', played_at) AS INTEGER) as hour,
            COUNT(*) as count
        FROM history
        GROUP BY hour
        ORDER BY hour
    """, conn)

    all_hours = pd.DataFrame({'hour': range(24)})
    hourly_chart = all_hours.merge(hourly_chart, on='hour', how='left').fillna(0)
    hourly_chart['count'] = hourly_chart['count'].astype(int)

    # 20. Týdenní breakdown (OPTIMALIZOVÁNO)
    weekly_chart = pd.read_sql_query("""
        SELECT
            CAST(strftime('%w', played_at) AS INTEGER) as day_num,
            CASE CAST(strftime('%w', played_at) AS INTEGER)
                WHEN 0 THEN 'Ne'
                WHEN 1 THEN 'Po'
                WHEN 2 THEN 'Út'
                WHEN 3 THEN 'St'
                WHEN 4 THEN 'Čt'
                WHEN 5 THEN 'Pá'
                WHEN 6 THEN 'So'
            END as day_name,
            COUNT(*) as count
        FROM history
        GROUP BY day_num
        ORDER BY day_num
    """, conn)

    # 21. Měsíční trend - jen posledních 6 měsíců (OPTIMALIZOVÁNO)
    monthly_chart = pd.read_sql_query("""
        SELECT
            strftime('%Y-%m', played_at) as month,
            COUNT(*) as count
        FROM history
        WHERE played_at >= date('now', '-6 months')
        GROUP BY month
        ORDER BY month
    """, conn)

    # 22. Listening streak (OPTIMALIZOVÁNO - jen distinct dates)
    all_dates = pd.read_sql_query("""
        SELECT DISTINCT DATE(played_at) as date
        FROM history
        ORDER BY date DESC
        LIMIT 365
    """, conn)

    max_streak = 1
    current_streak = 1
    if not all_dates.empty:
        dates = pd.to_datetime(all_dates['date']).sort_values()
        for i in range(1, len(dates)):
            if (dates.iloc[i] - dates.iloc[i - 1]).days == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1

    conn.close()

    return {
        'start_date': start_date,
        'top_artists': top_artists,
        'top_tracks': top_tracks,
        'top_albums': top_albums,
        'total_hours': total_hours,
        'total_min': total_min,
        'total_plays': total_plays,
        'unique_tracks': unique_tracks,
        'unique_artists': unique_artists,
        'unique_albums': unique_albums,
        'avg_per_day': avg_per_day,
        'last_24h': last_24h,
        'last_7d': last_7d,
        'repeat_rate': repeat_rate,
        'top_day_date': top_day_date,
        'top_day_count': top_day_count,
        'favorite_weekday': favorite_weekday,
        'favorite_weekday_count': favorite_weekday_count,
        'night_percentage': night_percentage,
        'avg_min': avg_min,
        'avg_sec': avg_sec,
        'hourly_stats': hourly_stats,
        'max_streak': max_streak,
        'hourly_chart': hourly_chart,
        'weekly_chart': weekly_chart,
        'monthly_chart': monthly_chart,
        'app_title': APP_TITLE,
    }


@app.route('/login', methods=['GET', 'POST'])
def login():
    if NOT_CONFIGURED:
        return render_template_string(SETUP_TEMPLATE)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error=True, app_title=APP_TITLE)

    return render_template_string(LOGIN_TEMPLATE, error=False, app_title=APP_TITLE)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@app.route('/')
@login_required
def home():
    data = get_data()
    return render_template_string(MAIN_TEMPLATE, **data)


SETUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <title>Nutná konfigurace</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { background:#000; color:#fff; font-family: -apple-system, sans-serif; display:flex;
               align-items:center; justify-content:center; min-height:100vh; margin:0; }
        .box { max-width:560px; padding:40px; background:rgba(24,24,24,0.9); border-radius:16px;
               border:1px solid rgba(255,255,255,0.1); }
        h1 { color:#1DB954; margin-top:0; }
        code { background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:6px; }
        ol { line-height:1.8; }
    </style>
</head>
<body>
    <div class="box">
        <h1>Aplikace ještě není nakonfigurovaná</h1>
        <p>Chybí <code>ADMIN_USERNAME</code>, <code>ADMIN_PASSWORD</code> nebo <code>FLASK_SECRET_KEY</code> v souboru <code>.env</code>.</p>
        <ol>
            <li>Na serveru spusť <code>deploy/install.sh</code>, nebo</li>
            <li>Ručně zkopíruj <code>.env.example</code> na <code>.env</code> a doplň hodnoty.</li>
            <li>Restartuj službu: <code>sudo systemctl restart spotify-web</code>.</li>
        </ol>
    </div>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <title>Login - {{ app_title }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background: #000000;
            font-family: 'Inter', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            position: relative;
            overflow: hidden;
        }

        body::before {
            content: '';
            position: fixed;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle at 30% 20%, rgba(29, 185, 84, 0.15), transparent 40%),
                        radial-gradient(circle at 70% 60%, rgba(29, 185, 84, 0.08), transparent 40%);
            animation: float 20s ease-in-out infinite;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(5deg); }
        }

        .login-container {
            position: relative;
            z-index: 1;
            background: rgba(24, 24, 24, 0.8);
            backdrop-filter: blur(20px);
            padding: 50px 40px;
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            width: 100%;
            max-width: 420px;
            animation: fadeIn 0.5s ease-out;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .logo {
            text-align: center;
            margin-bottom: 40px;
        }

        .logo h1 {
            font-size: 2.2rem;
            font-weight: 900;
            background: linear-gradient(135deg, #1DB954 0%, #1ed760 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 8px;
        }

        .logo p {
            color: #b3b3b3;
            font-size: 0.9rem;
            letter-spacing: 1px;
        }

        .form-group {
            margin-bottom: 25px;
        }

        label {
            display: block;
            color: #FFFFFF;
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }

        input {
            width: 100%;
            padding: 14px 16px;
            background: rgba(40, 40, 40, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            color: #FFFFFF;
            font-size: 1rem;
            font-family: 'Inter', sans-serif;
            transition: all 0.3s ease;
        }

        input:focus {
            outline: none;
            border-color: #1DB954;
            background: rgba(40, 40, 40, 0.8);
            box-shadow: 0 0 0 3px rgba(29, 185, 84, 0.1);
        }

        button {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #1DB954 0%, #1ed760 100%);
            border: none;
            border-radius: 12px;
            color: #000000;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(29, 185, 84, 0.4);
        }

        button:active {
            transform: translateY(0);
        }

        .error {
            background: rgba(255, 59, 48, 0.1);
            border: 1px solid rgba(255, 59, 48, 0.3);
            color: #ff3b30;
            padding: 12px 16px;
            border-radius: 12px;
            margin-bottom: 20px;
            text-align: center;
            font-size: 0.9rem;
            animation: shake 0.5s ease;
        }

        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-10px); }
            75% { transform: translateX(10px); }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>{{ app_title }}</h1>
            <p>Přihlášení</p>
        </div>
        {% if error %}
        <div class="error">
            ❌ Špatné uživatelské jméno nebo heslo
        </div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label for="username">Uživatelské jméno</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">Heslo</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Přihlásit se</button>
        </form>
    </div>
</body>
</html>
"""

MAIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <title>{{ app_title }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --spotify-green: #1DB954;
            --spotify-green-dim: #1ed760;
            --bg-black: #000000;
            --card-bg: rgba(24, 24, 24, 0.6);
            --card-hover: rgba(40, 40, 40, 0.8);
            --text-main: #FFFFFF;
            --text-dim: #b3b3b3;
            --glow-green: rgba(29, 185, 84, 0.4);
        }

        /* LOADING SCREEN */
        #loading-screen {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: #000000;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            transition: opacity 0.5s ease, visibility 0.5s ease;
        }

        #loading-screen.hidden {
            opacity: 0;
            visibility: hidden;
        }

        .loader {
            position: relative;
            width: 120px;
            height: 120px;
        }

        .vinyl {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: linear-gradient(135deg, #1DB954 0%, #1ed760 50%, #17a84a 100%);
            position: relative;
            animation: spin 2s linear infinite;
            box-shadow: 0 0 40px rgba(29, 185, 84, 0.6);
        }

        .vinyl::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: #000;
            box-shadow: inset 0 0 10px rgba(29, 185, 84, 0.5);
        }

        .vinyl::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 80px;
            height: 80px;
            border-radius: 50%;
            border: 2px solid rgba(0, 0, 0, 0.2);
        }

        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .loading-text {
            position: absolute;
            bottom: -50px;
            left: 50%;
            transform: translateX(-50%);
            color: var(--spotify-green);
            font-weight: 700;
            font-size: 1.1rem;
            letter-spacing: 2px;
            white-space: nowrap;
        }

        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
        }

        body {
            background: #000000;
            color: var(--text-main);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0;
            padding: 0;
            overflow-x: hidden;
            position: relative;
        }

        body::before {
            content: '';
            position: fixed;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle at 30% 20%, rgba(29, 185, 84, 0.15), transparent 40%),
                        radial-gradient(circle at 70% 60%, rgba(29, 185, 84, 0.08), transparent 40%);
            animation: float 20s ease-in-out infinite;
            z-index: 0;
        }

        .container {
            max-width: 1600px;
            margin: auto;
            padding: 40px 20px 80px;
            position: relative;
            z-index: 1;
        }

        /* LOGOUT BUTTON */
        .logout-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: rgba(24, 24, 24, 0.9);
            backdrop-filter: blur(10px);
            padding: 12px 24px;
            border-radius: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: var(--text-dim);
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 600;
            transition: all 0.3s ease;
            z-index: 1000;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .logout-btn:hover {
            background: rgba(255, 59, 48, 0.15);
            border-color: rgba(255, 59, 48, 0.3);
            color: #ff3b30;
            transform: translateY(-2px);
        }

        /* HEADER */
        .header {
            text-align: center;
            margin-bottom: 60px;
            animation: fadeInUp 0.8s ease-out;
        }

        .tracking-date {
            color: var(--spotify-green);
            font-weight: 700;
            text-transform: uppercase;
            font-size: 0.7rem;
            letter-spacing: 2.5px;
            display: inline-block;
            margin-bottom: 12px;
            padding: 6px 16px;
            background: rgba(29, 185, 84, 0.1);
            border-radius: 30px;
            border: 1px solid rgba(29, 185, 84, 0.3);
        }

        h1 {
            font-size: 3.5rem;
            font-weight: 900;
            margin: 10px 0 0 0;
            letter-spacing: -2px;
            background: linear-gradient(135deg, #1DB954 0%, #1ed760 50%, #17a84a 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1.1;
        }

        /* SECTION DIVIDER */
        .section {
            margin-bottom: 70px;
        }

        .section-title {
            font-size: 1.8rem;
            font-weight: 800;
            margin-bottom: 30px;
            color: var(--text-main);
            letter-spacing: -0.5px;
            padding-bottom: 15px;
            border-bottom: 2px solid rgba(29, 185, 84, 0.3);
        }

        /* OVERVIEW STATS */
        .stats-overview {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            padding: 25px 20px;
            border-radius: 20px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            transition: all 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-3px);
            border-color: rgba(29, 185, 84, 0.3);
            box-shadow: 0 8px 30px rgba(29, 185, 84, 0.2);
        }

        .stat-value {
            color: var(--spotify-green);
            font-size: 2rem;
            font-weight: 900;
            display: block;
            margin-bottom: 6px;
            letter-spacing: -1px;
        }

        .stat-label {
            color: var(--text-dim);
            text-transform: uppercase;
            font-size: 0.65rem;
            font-weight: 700;
            letter-spacing: 1.5px;
        }

        /* INSIGHTS CARDS */
        .insights-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }

        .insight-card {
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            padding: 25px;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            transition: all 0.3s ease;
        }

        .insight-card:hover {
            border-color: rgba(29, 185, 84, 0.2);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
            transform: translateY(-3px);
        }

        .insight-icon {
            font-size: 1.8rem;
            margin-bottom: 10px;
            display: block;
        }

        .insight-card h3 {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--text-dim);
            margin-bottom: 10px;
        }

        .insight-card .value {
            font-size: 1.4rem;
            font-weight: 800;
            color: var(--text-main);
            margin-bottom: 5px;
        }

        .insight-card .subtext {
            font-size: 0.85rem;
            color: var(--text-dim);
        }

        /* CHARTS */
        .charts-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }

        .chart-card {
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            padding: 35px 30px;
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            transition: all 0.3s ease;
        }

        .chart-card:hover {
            border-color: rgba(29, 185, 84, 0.2);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
        }

        .chart-card h3 {
            font-size: 1.3rem;
            font-weight: 800;
            margin-bottom: 25px;
            padding-left: 18px;
            border-left: 4px solid var(--spotify-green);
            letter-spacing: -0.5px;
        }

        .chart-container {
            position: relative;
            height: 300px;
        }

        canvas {
            max-height: 300px;
        }

        /* TOP LISTS */
        .top-lists {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
        }

        .list-card {
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            padding: 35px 30px;
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            transition: all 0.3s ease;
        }

        .list-card:hover {
            border-color: rgba(29, 185, 84, 0.2);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
        }

        .list-card h2 {
            font-size: 1.4rem;
            font-weight: 800;
            margin-bottom: 25px;
            padding-left: 18px;
            border-left: 4px solid var(--spotify-green);
            letter-spacing: -0.5px;
        }

        ul {
            list-style: none;
            padding: 0;
        }

        li {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            padding: 12px 10px;
            border-radius: 14px;
            transition: all 0.3s ease;
        }

        li:hover {
            background: var(--card-hover);
            transform: translateX(5px);
        }

        img {
            border-radius: 8px;
            margin-right: 15px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.5);
            object-fit: cover;
            transition: all 0.3s ease;
        }

        li:hover img {
            box-shadow: 0 4px 20px rgba(29, 185, 84, 0.4);
            transform: scale(1.05);
        }

        .rank {
            margin-right: 12px;
            color: var(--text-dim);
            font-weight: 800;
            font-size: 0.95rem;
            width: 25px;
            text-align: center;
        }

        .track-info {
            display: flex;
            flex-direction: column;
            flex: 1;
        }

        .track-name {
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 3px;
            letter-spacing: -0.2px;
        }

        .artist-sub {
            color: var(--text-dim);
            font-size: 0.85rem;
            font-weight: 400;
        }

        .count {
            color: var(--spotify-green);
            font-weight: 800;
            font-size: 0.9rem;
            background: rgba(29, 185, 84, 0.15);
            padding: 5px 12px;
            border-radius: 20px;
            border: 1px solid rgba(29, 185, 84, 0.3);
            white-space: nowrap;
            transition: all 0.3s ease;
        }

        li:hover .count {
            background: rgba(29, 185, 84, 0.25);
            border-color: rgba(29, 185, 84, 0.5);
        }

        /* RESPONSIVE */
        @media (max-width: 768px) {
            h1 {
                font-size: 2.5rem;
            }
            .top-lists {
                grid-template-columns: 1fr;
            }
            .stats-overview {
                grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            }
            .stat-value {
                font-size: 1.7rem;
            }
            .container {
                padding: 30px 15px 60px;
            }
            .list-card {
                padding: 25px 20px;
            }
            .section {
                margin-bottom: 50px;
            }
            .insights-grid {
                grid-template-columns: 1fr;
            }
            .charts-section {
                grid-template-columns: 1fr;
            }
            .logout-btn {
                bottom: 20px;
                right: 20px;
            }
        }

        @media (max-width: 480px) {
            h1 {
                font-size: 2rem;
            }
        }

        /* SCROLLBAR */
        ::-webkit-scrollbar {
            width: 10px;
        }

        ::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.3);
        }

        ::-webkit-scrollbar-thumb {
            background: rgba(29, 185, 84, 0.5);
            border-radius: 10px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: rgba(29, 185, 84, 0.7);
        }
    </style>
</head>
<body>
    <!-- LOADING SCREEN -->
    <div id="loading-screen">
        <div class="loader">
            <div class="vinyl"></div>
            <div class="loading-text">NAČÍTÁM...</div>
        </div>
    </div>

    <div class="container">
        <!-- HEADER -->
        <div class="header">
            <span class="tracking-date">Měříme od {{ start_date }}</span>
            <h1>{{ app_title }}</h1>
        </div>

        <!-- SECTION: PŘEHLED -->
        <div class="section">
            <h2 class="section-title">Celkový Přehled</h2>
            <div class="stats-overview">
                <div class="stat-card">
                    <span class="stat-value">{{ total_hours }}h {{ total_min }}m</span>
                    <span class="stat-label">Celkový čas</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{{ total_plays }}</span>
                    <span class="stat-label">Přehráno</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{{ unique_tracks }}</span>
                    <span class="stat-label">Unikátních</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{{ unique_artists }}</span>
                    <span class="stat-label">Artistů</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{{ unique_albums }}</span>
                    <span class="stat-label">Alb</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{{ avg_per_day }}</span>
                    <span class="stat-label">Průměr/den</span>
                </div>
            </div>
        </div>

        <!-- SECTION: INSIGHTS -->
        <div class="section">
            <h2 class="section-title">Zajímavosti</h2>
            <div class="insights-grid">
                <div class="insight-card">
                    <span class="insight-icon">🔁</span>
                    <h3>Repeat rate</h3>
                    <div class="value">{{ repeat_rate }}%</div>
                    <div class="subtext">skladeb posloucháš opakovaně</div>
                </div>

                <div class="insight-card">
                    <span class="insight-icon">🏆</span>
                    <h3>Nejlepší den</h3>
                    <div class="value">{{ top_day_count }} skladeb</div>
                    <div class="subtext">{{ top_day_date }}</div>
                </div>

                <div class="insight-card">
                    <span class="insight-icon">📅</span>
                    <h3>Nejčastější den</h3>
                    <div class="value">{{ favorite_weekday }}</div>
                    <div class="subtext">{{ favorite_weekday_count }} přehrání celkem</div>
                </div>

                <div class="insight-card">
                    <span class="insight-icon">🌙</span>
                    <h3>Night Owl Score</h3>
                    <div class="value">{{ night_percentage }}%</div>
                    <div class="subtext">poslouchání mezi 22:00-6:00</div>
                </div>

                <div class="insight-card">
                    <span class="insight-icon">⏱️</span>
                    <h3>Průměrná délka</h3>
                    <div class="value">{{ avg_min }}:{{ "%02d"|format(avg_sec) }}</div>
                    <div class="subtext">průměrná skladba</div>
                </div>

                <div class="insight-card">
                    <span class="insight-icon">🕐</span>
                    <h3>Peak hodiny</h3>
                    <div class="value">
                        {% for i, r in hourly_stats.iterrows() %}
                            {{ r['hour'] }}:00{% if not loop.last %}, {% endif %}
                        {% endfor %}
                    </div>
                    <div class="subtext">kdy posloucháš nejvíc</div>
                </div>

                <div class="insight-card">
                    <span class="insight-icon">🔥</span>
                    <h3>Listening Streak</h3>
                    <div class="value">{{ max_streak }} dní</div>
                    <div class="subtext">nejdelší série v kuse</div>
                </div>

                <div class="insight-card">
                    <span class="insight-icon">📈</span>
                    <h3>Tento týden</h3>
                    <div class="value">{{ last_7d }} skladeb</div>
                    <div class="subtext">{{ (last_7d / 7)|int }} průměr/den</div>
                </div>
            </div>
        </div>

        <!-- SECTION: CHARTS -->
        <div class="section">
            <h2 class="section-title">Grafy & Trendy</h2>
            <div class="charts-section">
                <div class="chart-card">
                    <h3>🕐 Aktivita Během Dne</h3>
                    <div class="chart-container">
                        <canvas id="hourlyChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <h3>📅 Aktivita v Týdnu</h3>
                    <div class="chart-container">
                        <canvas id="weeklyChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <h3>📈 Měsíční Trend</h3>
                    <div class="chart-container">
                        <canvas id="monthlyChart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- SECTION: TOP LISTS -->
        <div class="section">
            <h2 class="section-title">Top Žebříčky</h2>
            <div class="top-lists">
                <div class="list-card">
                    <h2>Top Interpreti</h2>
                    <ul>
                    {% for i, r in top_artists.iterrows() %}
                        <li>
                            <span class="rank">{{ i+1 }}</span>
                            <img src="{{ r['image_url'] }}" width="55" height="55" alt="{{ r['artist_name'] }}" loading="lazy">
                            <div class="track-info">
                                <span class="track-name">{{ r['artist_name'] }}</span>
                            </div>
                            <span class="count">{{ r['count'] }}×</span>
                        </li>
                    {% endfor %}
                    </ul>
                </div>

                <div class="list-card">
                    <h2>Top Skladby</h2>
                    <ul>
                    {% for i, r in top_tracks.iterrows() %}
                        <li>
                            <span class="rank">{{ i+1 }}</span>
                            <img src="{{ r['image_url'] }}" width="55" height="55" alt="{{ r['track_name'] }}" loading="lazy">
                            <div class="track-info">
                                <span class="track-name">{{ r['track_name'][:30] }}{% if r['track_name']|length > 30 %}...{% endif %}</span>
                                <span class="artist-sub">{{ r['artist_name'] }}</span>
                            </div>
                            <span class="count">{{ r['count'] }}×</span>
                        </li>
                    {% endfor %}
                    </ul>
                </div>

                <div class="list-card">
                    <h2>Top Alba</h2>
                    <ul>
                    {% for i, r in top_albums.iterrows() %}
                        <li>
                            <span class="rank">{{ i+1 }}</span>
                            <img src="{{ r['image_url'] }}" width="55" height="55" alt="{{ r['album_name'] }}" loading="lazy">
                            <div class="track-info">
                                <span class="track-name">{{ r['album_name'][:30] }}{% if r['album_name']|length > 30 %}...{% endif %}</span>
                                <span class="artist-sub">{{ r['artist_name'] }}</span>
                            </div>
                            <span class="count">{{ r['count'] }}×</span>
                        </li>
                    {% endfor %}
                    </ul>
                </div>
            </div>
        </div>
    </div>

    <!-- LOGOUT BUTTON -->
    <a href="/logout" class="logout-btn">
        <span>🚪</span>
        Odhlásit se
    </a>

    <script>
        // Hide loading screen when page is ready
        window.addEventListener('load', function() {
            setTimeout(function() {
                document.getElementById('loading-screen').classList.add('hidden');
            }, 800);
        });

        // Chart.js defaults
        Chart.defaults.color = '#b3b3b3';
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
        Chart.defaults.font.family = 'Inter, sans-serif';

        // Hourly Chart
        const hourlyCtx = document.getElementById('hourlyChart').getContext('2d');
        const hourlyGradient = hourlyCtx.createLinearGradient(0, 0, 0, 300);
        hourlyGradient.addColorStop(0, 'rgba(29, 185, 84, 0.8)');
        hourlyGradient.addColorStop(1, 'rgba(29, 185, 84, 0.1)');

        new Chart(hourlyCtx, {
            type: 'line',
            data: {
                labels: {{ hourly_chart['hour'].tolist() }},
                datasets: [{
                    label: 'Přehrání',
                    data: {{ hourly_chart['count'].tolist() }},
                    backgroundColor: hourlyGradient,
                    borderColor: '#1DB954',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 7,
                    pointBackgroundColor: '#1DB954',
                    pointBorderColor: '#000',
                    pointBorderWidth: 2,
                    pointHoverBackgroundColor: '#1ed760',
                    pointHoverBorderColor: '#1DB954',
                    pointHoverBorderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(24, 24, 24, 0.95)',
                        titleColor: '#1DB954',
                        bodyColor: '#FFFFFF',
                        borderColor: '#1DB954',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            title: function(context) {
                                return context[0].label + ':00';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: '#b3b3b3'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#b3b3b3',
                            callback: function(value, index) {
                                return index % 3 === 0 ? this.getLabelForValue(value) + 'h' : '';
                            }
                        }
                    }
                }
            }
        });

        // Weekly Chart
        const weeklyCtx = document.getElementById('weeklyChart').getContext('2d');
        new Chart(weeklyCtx, {
            type: 'bar',
            data: {
                labels: {{ weekly_chart['day_name'].tolist()|tojson }},
                datasets: [{
                    label: 'Přehrání',
                    data: {{ weekly_chart['count'].tolist() }},
                    backgroundColor: function(context) {
                        const chart = context.chart;
                        const {ctx, chartArea} = chart;
                        if (!chartArea) return '#1DB954';
                        const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
                        gradient.addColorStop(0, 'rgba(29, 185, 84, 0.6)');
                        gradient.addColorStop(1, 'rgba(29, 185, 84, 1)');
                        return gradient;
                    },
                    borderColor: '#1DB954',
                    borderWidth: 2,
                    borderRadius: 8,
                    hoverBackgroundColor: '#1ed760',
                    hoverBorderColor: '#1ed760',
                    hoverBorderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(24, 24, 24, 0.95)',
                        titleColor: '#1DB954',
                        bodyColor: '#FFFFFF',
                        borderColor: '#1DB954',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: '#b3b3b3'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#b3b3b3',
                            font: {
                                weight: 'bold'
                            }
                        }
                    }
                }
            }
        });

        // Monthly Chart
        const monthlyCtx = document.getElementById('monthlyChart').getContext('2d');
        const monthlyGradient = monthlyCtx.createLinearGradient(0, 0, 0, 300);
        monthlyGradient.addColorStop(0, 'rgba(29, 185, 84, 0.7)');
        monthlyGradient.addColorStop(1, 'rgba(29, 185, 84, 0.05)');

        new Chart(monthlyCtx, {
            type: 'line',
            data: {
                labels: {{ monthly_chart['month'].tolist()|tojson }},
                datasets: [{
                    label: 'Přehrání',
                    data: {{ monthly_chart['count'].tolist() }},
                    backgroundColor: monthlyGradient,
                    borderColor: '#1DB954',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 5,
                    pointHoverRadius: 8,
                    pointBackgroundColor: '#1DB954',
                    pointBorderColor: '#000',
                    pointBorderWidth: 2,
                    pointHoverBackgroundColor: '#1ed760',
                    pointHoverBorderColor: '#1DB954',
                    pointHoverBorderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(24, 24, 24, 0.95)',
                        titleColor: '#1DB954',
                        bodyColor: '#FFFFFF',
                        borderColor: '#1DB954',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            title: function(context) {
                                const monthYear = context[0].label;
                                const [year, month] = monthYear.split('-');
                                const months = ['Led', 'Úno', 'Bře', 'Dub', 'Kvě', 'Čvn', 'Čvc', 'Srp', 'Zář', 'Říj', 'Lis', 'Pro'];
                                return months[parseInt(month) - 1] + ' ' + year;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: '#b3b3b3'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#b3b3b3',
                            callback: function(value, index) {
                                const monthYear = this.getLabelForValue(value);
                                const [year, month] = monthYear.split('-');
                                const months = ['Led', 'Úno', 'Bře', 'Dub', 'Kvě', 'Čvn', 'Čvc', 'Srp', 'Zář', 'Říj', 'Lis', 'Pro'];
                                return months[parseInt(month) - 1];
                            }
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host=WEB_HOST, port=WEB_PORT)
