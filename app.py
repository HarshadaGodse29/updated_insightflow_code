import os
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.utils import secure_filename
from supabase_storage import supabase_storage
from modules.transcription import TranscriptionModule
from modules.summarizer_module import SummarizerModule
from modules.action_item_module import ActionItemModule
from modules.sentiment_module import SentimentModule
from modules.translation_module import TranslationModule

# Initialize app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize AI modules
asr = TranscriptionModule()
summarizer = SummarizerModule()
action_extractor = ActionItemModule()
sentiment_analyzer = SentimentModule()
translator = TranslationModule()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active live sessions
active_sessions = {}

# ========== BEFORE REQUEST HANDLER ==========
@app.before_request
def before_request():
    """Handle route permissions"""
    public_routes = ['/', '/index', '/home', '/login', '/signup', 
                     '/api/login', '/api/signup', '/api/contact', '/static']

    for route in public_routes:
        if request.path.startswith(route):
            return None

    if request.path.startswith('/api/'):
        if not session.get('user_id'):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        return None

    if not session.get('user_id'):
        return redirect(url_for('login_page'))
    
    return None

# ========== AUTH DECORATOR ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    user_id = session.get('user_id')
    return db.session.get(User, user_id) if user_id else None

# ========== AUTH ROUTES ==========
@app.route("/")
def root():
    """Landing page - always shows index.html"""
    return render_template("index.html")

@app.route("/index")
def index_redirect():
    """Redirect /index to root"""
    return redirect(url_for('root'))

@app.route("/home")
def home_redirect():
    """Redirect /home to root"""
    return redirect(url_for('root'))

@app.route("/login")
def login_page():
    """Login page"""
    return render_template("login.html")

@app.route("/signup")
def signup_page():
    """Signup page"""
    return render_template("signup.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    """Handle login request"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    remember = data.get('remember', False)
    
    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required"}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if user and user.check_password(password):
        session['user_id'] = user.id
        session['user_email'] = user.email
        session.permanent = remember
        
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Login successful",
            "user": user.to_dict()
        })
    
    return jsonify({"success": False, "error": "Invalid email or password"}), 401

@app.route("/api/signup", methods=["POST"])
def api_signup():
    """Handle signup request"""
    data = request.get_json()
    
    first_name = data.get('firstName', '')
    last_name = data.get('lastName', '')
    email = data.get('email', '')
    password = data.get('password', '')
    security_level = data.get('securityLevel', 'standard')
    security_pin = data.get('securityPin', '')
    use_case = data.get('useCase', 'work')
    newsletter = data.get('newsletter', False)

    username = email.split('@')[0]
    full_name = f"{first_name} {last_name}".strip()
    
    # Validate required fields
    if not first_name or not last_name or not email or not password:
        return jsonify({"success": False, "error": "All fields are required"}), 400
    
    # Validate email format
    if '@' not in email or '.' not in email:
        return jsonify({"success": False, "error": "Invalid email format"}), 400
    
    # Validate password length
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "error": "Email already registered"}), 400
    
    if User.query.filter_by(username=username).first():
        import random
        username = f"{username}{random.randint(100, 999)}"
    
    try:
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            job_title='New User',
            department=use_case
        )
        user.set_password(password)
        
        logger.info(f"New user registered: {email}")
        
        return jsonify({
            "success": True,
            "message": "Account created successfully",
            "user": user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        db.session.rollback()
        return jsonify({"success": False, "error": "Failed to create account. Please try again."}), 500

@app.route("/api/logout", methods=["POST"])
def api_logout():
    """Handle logout request"""
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})

# ========== CONTACT FORM API ==========
@app.route("/api/contact", methods=["POST"])
def api_contact():
    """Handle contact form submission"""
    data = request.get_json()
    
    name = data.get('name')
    email = data.get('email')
    company = data.get('company')
    interest = data.get('interest')
    message = data.get('message')

    if not name or not email or not message:
        return jsonify({"success": False, "error": "Please fill in all required fields"}), 400

    logger.info(f"Contact form submission from {name} ({email}) - Interest: {interest}")
 
    return jsonify({
        "success": True,
        "message": "Thank you for contacting us! We'll get back to you soon."
    })

# ========== PAGE ROUTES ==========
@app.route("/Dashboard")
@login_required
def dashboard():
    """Dashboard page"""
    return render_template("dashboard.html")

@app.route("/Upload-Transcribe")
@login_required
def upload_transcribe():
    """Upload and transcribe page"""
    return render_template("upload_transcribe.html")

@app.route("/Live-Transcription")
@login_required
def live_transcription():
    """Live transcription page"""
    return render_template("live_transcription.html")

@app.route("/Summarization")
@login_required
def summarization_page():
    """Summarization page"""
    return render_template("summarization.html")

@app.route("/My-Tasks")
@login_required
def my_tasks_page():
    """My tasks page"""
    return render_template("my_tasks.html")

@app.route("/Sentiment-Analysis")
@login_required
def sentiment_page():
    """Sentiment analysis page"""
    return render_template("sentiment_analysis.html")

@app.route("/Speaker-Identification")
@login_required
def speaker_identification():
    """Speaker identification page"""
    return render_template("speaker_identification.html")

@app.route("/Translation")
@login_required
def translation_page():
    """Translation page"""
    return render_template("translation.html")

@app.route("/Files-History")
@login_required
def files_history():
    """Files history page"""
    return render_template("files_history.html")

@app.route("/Analytics")
@login_required
def analytics_page():
    """Analytics page"""
    return render_template("analytics.html")

@app.route("/Calendar")
@login_required
def calendar_page():
    """Calendar page"""
    return render_template("calendar.html")

@app.route("/Profile")
@login_required
def profile_page():
    """Profile page"""
    return render_template("profile.html")

# ========== USER PROFILE API ==========
@app.route("/api/user/profile", methods=["GET"])
@api_login_required
def get_user_profile():
    """Get user profile"""
    user = get_current_user()
    settings = user.settings
    
    return jsonify({
        "success": True,
        "user": user.to_dict(),
        "settings": {
            "email_notifications": settings.email_notifications,
            "desktop_notifications": settings.desktop_notifications,
            "theme": settings.theme,
            "sidebar_collapsed": settings.sidebar_collapsed,
            "security_level": getattr(settings, 'security_level', 'standard')
        }
    })

@app.route("/api/user/profile", methods=["PUT"])
@api_login_required
def update_user_profile():
    """Update user profile"""
    data = request.get_json()
    user = get_current_user()
    
    if 'full_name' in data:
        user.full_name = data['full_name']
    if 'job_title' in data:
        user.job_title = data['job_title']
    if 'department' in data:
        user.department = data['department']
    if 'email' in data and data['email'] != user.email:
        if User.query.filter_by(email=data['email']).first():
            return jsonify({"success": False, "error": "Email in use"}), 400
        user.email = data['email']
        session['user_email'] = data['email']

    return jsonify({"success": True, "user": user.to_dict()})

@app.route("/api/user/settings", methods=["PUT"])
@api_login_required
def update_user_settings():
    """Update user settings"""
    data = request.get_json()
    user = get_current_user()
    settings = user.settings
    
    if 'email_notifications' in data:
        settings.email_notifications = data['email_notifications']
    if 'desktop_notifications' in data:
        settings.desktop_notifications = data['desktop_notifications']
    if 'theme' in data:
        settings.theme = data['theme']
    if 'sidebar_collapsed' in data:
        settings.sidebar_collapsed = data['sidebar_collapsed']

    return jsonify({"success": True})

# ========== TRANSCRIPTION API ==========
@app.route("/api/transcribe", methods=["POST"])
@api_login_required
def transcribe():
    """Handle audio transcription"""
    if 'audio' not in request.files:
        return jsonify({"success": False, "error": "No audio file"}), 400
    
    audio = request.files['audio']
    
    if audio.filename == '':
        return jsonify({"success": False, "error": "No file selected"}), 400
    
    # Get language preference
    language = request.form.get('language', 'auto')
    
    # Read file data
    audio_data = audio.read()
    filename = secure_filename(audio.filename)
    user_id = session['user_id']
    
    # Save temporarily
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_{filename}')
    with open(temp_path, 'wb') as f:
        f.write(audio_data)
    
    try:
        # Transcribe using AssemblyAI
        language_code = None if language == 'auto' else language
        transcript = asr.transcribe_file(temp_path, language_code=language_code)
        
        # Upload to Supabase
        audio_key, audio_url = supabase_storage.upload_audio(audio_data, filename, user_id)
        transcript_key, transcript_url = supabase_storage.upload_transcript(transcript, filename, user_id)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Calculate stats
        word_count = transcript['metadata']['total_words']
        speaker_count = transcript['metadata']['speaker_count']
        detected_language = transcript['metadata']['language']
        language_name = transcript['metadata']['language_name']
        
        # Save to database
        db_transcript = Transcript(
            user_id=user_id,
            filename=filename,
            title=filename.rsplit('.', 1)[0].replace('_', ' '),
            duration=transcript['metadata']['duration'],
            word_count=word_count,
            speaker_count=speaker_count,
            file_size=len(audio_data),
            audio_key=audio_key,
            transcript_key=transcript_key,
            transcript_data=transcript
        )
  
        return jsonify({
            "success": True,
            "transcript": transcript,
            "db_id": db_transcript.id,
            "audio_url": audio_url,
            "transcript_url": transcript_url,
            "detected_language": detected_language,
            "language_name": language_name,
            "message": f"Transcription completed. Detected language: {language_name}"
        })
        
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/transcripts", methods=["GET"])
@api_login_required
def get_transcripts():
    """Get all transcripts for user"""
    user_id = session['user_id']
    transcripts = Transcript.query.filter_by(user_id=user_id)\
        .order_by(Transcript.created_at.desc()).all()
    
    result = []
    for t in transcripts:
        data = t.to_dict()
        if t.transcript_data and 'metadata' in t.transcript_data:
            data['language'] = t.transcript_data['metadata'].get('language', 'en')
            data['language_name'] = t.transcript_data['metadata'].get('language_name', 'English')
        if t.audio_key:
            data['audio_url'] = supabase_storage.get_download_url(t.audio_key)
        if t.transcript_key:
            data['transcript_url'] = supabase_storage.get_download_url(t.transcript_key)
        result.append(data)
    
    return jsonify({"success": True, "transcripts": result})

@app.route("/api/transcripts/<int:transcript_id>", methods=["GET"])
@api_login_required
def get_transcript(transcript_id):
    """Get specific transcript"""
    transcript = Transcript.query.get_or_404(transcript_id)
    
    if transcript.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    data = transcript.to_dict()
    if transcript.audio_key:
        data['audio_url'] = supabase_storage.get_download_url(transcript.audio_key)
    if transcript.transcript_key:
        data['transcript_url'] = supabase_storage.get_download_url(transcript.transcript_key)
    data['full_data'] = transcript.transcript_data
    
    return jsonify({"success": True, "transcript": data})

@app.route("/api/transcripts/<int:transcript_id>", methods=["PUT"])
@api_login_required
def update_transcript(transcript_id):
    """Update transcript title"""
    data = request.get_json()
    transcript = Transcript.query.get_or_404(transcript_id)
    
    if transcript.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    if 'title' in data:
        transcript.title = data['title']
        db.session.commit()
    
    return jsonify({"success": True, "transcript": transcript.to_dict()})

@app.route("/api/transcripts/<int:transcript_id>", methods=["DELETE"])
@api_login_required
def delete_transcript(transcript_id):
    """Delete transcript"""
    transcript = Transcript.query.get_or_404(transcript_id)
    
    if transcript.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    # Delete from Supabase storage
    if transcript.audio_key:
        supabase_storage.delete_file(transcript.audio_key)
    if transcript.transcript_key:
        supabase_storage.delete_file(transcript.transcript_key)
    
    return jsonify({"success": True})

# ========== SUMMARIZATION API ==========
@app.route("/api/summarize", methods=["POST"])
@api_login_required
def summarize():
    """Generate summary from transcript"""
    data = request.get_json()
    transcript_text = data.get("transcript", "")
    summary_type = data.get("summary_type", "executive")
    length = data.get("length", "medium")
    transcript_id = data.get("transcript_id")
    
    if not transcript_text:
        return jsonify({"success": False, "error": "Transcript required"}), 400
    
    try:
        result = summarizer.summarize(transcript_text, summary_type, length)
        
        if result["success"]:
            summary = Summary(
                user_id=session['user_id'],
                transcript_id=transcript_id,
                title=result.get('title', 'Meeting Summary'),
                content=result['summary'],
                summary_type=summary_type,
                length=length,
                word_count=result['metadata']['word_count']
            )

            
            return jsonify({
                "success": True,
                "summary": result["summary"],
                "title": result.get('title'),
                "db_id": summary.id,
                "metadata": result["metadata"]
            })
        else:
            return jsonify({"success": False, "error": result["error"]}), 500
            
    except Exception as e:
        logger.error(f"Summarization error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/summaries", methods=["GET"])
@api_login_required
def get_summaries():
    """Get all summaries for user"""
    user_id = session['user_id']
    summaries = Summary.query.filter_by(user_id=user_id)\
        .order_by(Summary.created_at.desc()).all()
    
    return jsonify({
        "success": True,
        "summaries": [s.to_dict() for s in summaries]
    })

# ========== ACTION ITEMS API ==========
@app.route("/api/extract-action-items", methods=["POST"])
@api_login_required
def extract_action_items():
    """Extract action items from transcript"""
    data = request.get_json()
    transcript_text = data.get("transcript", "")
    transcript_id = data.get("transcript_id")

    if not transcript_text:
        return jsonify({"success": False, "error": "Transcript required"}), 400

    try:
        items = action_extractor.extract(transcript_text)
        
        task_list = []
        for item in items:
            task = Task(
                user_id=session['user_id'],
                transcript_id=transcript_id,
                title=item.task,
                assignee=item.assignee,
                priority=item.priority or 'medium',
                status='pending',
                source_text=item.source_text
            )
            
            if item.deadline:
                try:
                    task.deadline = datetime.strptime(item.deadline, '%Y-%m-%d')
                except:
                    pass

        return jsonify({
            "success": True,
            "items": [
                {
                    "task": i.task,
                    "assignee": i.assignee,
                    "deadline": i.deadline,
                    "priority": i.priority,
                    "source_text": i.source_text
                }
                for i in items
            ],
            "tasks": task_list,
            "message": f"Extracted {len(items)} action items"
        })
    except Exception as e:
        logger.error(f"Action items extraction error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== TASKS API ==========
@app.route("/api/tasks", methods=["GET"])
@api_login_required
def get_tasks():
    """Get all tasks for user"""
    user_id = session['user_id']
    tasks = Task.query.filter_by(user_id=user_id)\
        .order_by(Task.created_at.desc()).all()
    
    return jsonify({
        "success": True,
        "tasks": [t.to_dict() for t in tasks]
    })

@app.route("/api/tasks", methods=["POST"])
@api_login_required
def create_task():
    """Create a new task"""
    data = request.get_json()
    
    task = Task(
        user_id=session['user_id'],
        title=data['title'],
        description=data.get('description'),
        assignee=data.get('assignee'),
        priority=data.get('priority', 'medium'),
        status=data.get('status', 'pending'),
        source_text=data.get('source_text'),
        transcript_id=data.get('transcript_id')
    )
    
    if data.get('deadline'):
        try:
            task.deadline = datetime.fromisoformat(data['deadline'])
        except:
            pass
    
    return jsonify({"success": True, "task": task.to_dict()})

@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@api_login_required
def update_task(task_id):
    """Update a task"""
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    data = request.get_json()
    
    if 'title' in data:
        task.title = data['title']
    if 'status' in data:
        task.status = data['status']
        if data['status'] == 'completed' and not task.completed_at:
            task.completed_at = datetime.utcnow()
    if 'assignee' in data:
        task.assignee = data['assignee']
    if 'priority' in data:
        task.priority = data['priority']
    if 'deadline' in data and data['deadline']:
        try:
            task.deadline = datetime.fromisoformat(data['deadline'])
        except:
            pass
    
    return jsonify({"success": True, "task": task.to_dict()})

@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@api_login_required
def delete_task(task_id):
    """Delete a task"""
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    return jsonify({"success": True})

# ========== SENTIMENT ANALYSIS API ==========
@app.route("/api/sentiment", methods=["POST"])
@api_login_required
def analyze_sentiment():
    """Analyze sentiment of transcript"""
    data = request.get_json()
    transcript_text = data.get("transcript", "")
    transcript_id = data.get("transcript_id")
    
    if not transcript_text:
        return jsonify({"success": False, "error": "Transcript required"}), 400
    
    try:
        result = sentiment_analyzer.analyze(transcript_text)
        
        sentiment = SentimentAnalysis(
            user_id=session['user_id'],
            transcript_id=transcript_id,
            text_preview=transcript_text[:200],
            sentiment=result['sentiment'],
            polarity_score=result['polarity_score'],
            word_count=len(transcript_text.split())
        )
        
        return jsonify({
            "success": True,
            "result": result,
            "db_id": sentiment.id
        })
        
    except Exception as e:
        logger.error(f"Sentiment analysis error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== TRANSLATION API ==========
@app.route("/api/translate", methods=["POST"])
@api_login_required
def translate_text():
    """Translate text"""
    data = request.get_json()
    text = data.get("text", "")
    source_lang = data.get("source_lang", "auto")
    target_lang = data.get("target_lang", "es")
    
    if not text:
        return jsonify({"success": False, "error": "No text provided"}), 400
    
    try:
        result = translator.translate(text, source_lang, target_lang)
        
        if result["success"]:
            translation = Translation(
                user_id=session['user_id'],
                source_text=text,
                translated_text=result['translated_text'],
                source_lang=result['source_lang'],
                target_lang=result['target_lang'],
                confidence=result.get('confidence', 0.9),
                word_count=len(text.split())
            )
            
            return jsonify({
                "success": True,
                "translation": result["translated_text"],
                "db_id": translation.id,
                "confidence": result.get("confidence"),
                "metadata": result.get("metadata", {})
            })
        else:
            return jsonify({"success": False, "error": result["error"]}), 500
            
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/translations", methods=["GET"])
@api_login_required
def get_translations():
    """Get all translations for user"""
    user_id = session['user_id']
    translations = Translation.query.filter_by(user_id=user_id)\
        .order_by(Translation.created_at.desc()).all()
    
    return jsonify({
        "success": True,
        "translations": [t.to_dict() for t in translations]
    })

# ========== CALENDAR API ==========
@app.route("/api/calendar/events", methods=["GET"])
@api_login_required
def get_calendar_events():
    """Get calendar events"""
    user_id = session['user_id']
    
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    query = CalendarEvent.query.filter_by(user_id=user_id)
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.filter(CalendarEvent.event_date >= start)
        except:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.filter(CalendarEvent.event_date <= end)
        except:
            pass
    
    events = query.order_by(CalendarEvent.event_date).all()
    
    return jsonify({
        "success": True,
        "events": [e.to_dict() for e in events]
    })

@app.route("/api/calendar/events", methods=["POST"])
@api_login_required
def create_calendar_event():
    """Create calendar event"""
    data = request.get_json()
    
    if not data.get('title') or not data.get('event_date'):
        return jsonify({"success": False, "error": "Title and date required"}), 400
    
    try:
        event_date = datetime.fromisoformat(data['event_date'])
    except:
        return jsonify({"success": False, "error": "Invalid date format"}), 400
    
    event = CalendarEvent(
        user_id=session['user_id'],
        title=data['title'],
        description=data.get('description'),
        event_date=event_date,
        event_type=data.get('event_type', 'meeting'),
        reminder=data.get('reminder', False),
        reminder_time=data.get('reminder_time')
    )
    
    return jsonify({"success": True, "event": event.to_dict()})

@app.route("/api/calendar/events/<int:event_id>", methods=["DELETE"])
@api_login_required
def delete_calendar_event(event_id):
    """Delete calendar event"""
    event = CalendarEvent.query.get_or_404(event_id)
    
    if event.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    return jsonify({"success": True})

# ========== DASHBOARD API ==========
@app.route("/api/dashboard/data", methods=["GET"])
@api_login_required
def get_dashboard_data():
    """Get dashboard data for user"""
    user_id = session['user_id']
    
    user = get_current_user()

    recent_transcripts = Transcript.query.filter_by(user_id=user_id)\
        .order_by(Transcript.created_at.desc()).limit(5).all()
    recent_live = LiveSession.query.filter_by(user_id=user_id)\
        .order_by(LiveSession.created_at.desc()).limit(5).all()
    recent_tasks = Task.query.filter_by(user_id=user_id)\
        .order_by(Task.created_at.desc()).limit(5).all()

    pending_tasks = Task.query.filter_by(user_id=user_id, status='pending').count()
    completed_tasks = Task.query.filter_by(user_id=user_id, status='completed').count()

    total_duration = 0
    for t in Transcript.query.filter_by(user_id=user_id).all():
        total_duration += t.duration or 0
    for l in LiveSession.query.filter_by(user_id=user_id).all():
        total_duration += l.duration or 0

    languages = set()
    for t in Transcript.query.filter_by(user_id=user_id).all():
        if t.transcript_data and 'metadata' in t.transcript_data:
            lang = t.transcript_data['metadata'].get('language', 'en')
            languages.add(lang)
    for l in LiveSession.query.filter_by(user_id=user_id).all():
        if l.detected_language and l.detected_language != 'auto':
            languages.add(l.detected_language)

    user_name = user.full_name if user and user.full_name else (user.username if user else 'User')
    
    return jsonify({
        "success": True,
        "user_name": user_name,
        "stats": {
            "transcripts": transcript_count,
            "live_sessions": live_session_count,
            "summaries": summary_count,
            "tasks": task_count,
            "pending_tasks": pending_tasks,
            "completed_tasks": completed_tasks,
            "total_duration": total_duration,
            "total_hours": round(total_duration / 3600, 1),
            "languages_used": len(languages)
        },
        "recent": {
            "transcripts": [t.to_dict() for t in recent_transcripts],
            "live_sessions": [s.to_dict() for s in recent_live],
            "tasks": [t.to_dict() for t in recent_tasks]
        }
    })

# ========== ANALYTICS API ==========
@app.route("/api/analytics/data", methods=["GET"])
@api_login_required
def get_analytics_data():
    """Get analytics data"""
    user_id = session['user_id']
    
    days = int(request.args.get('days', 30))
    start_date = datetime.utcnow() - timedelta(days=days)
    
    transcripts = Transcript.query.filter(
        Transcript.user_id == user_id,
        Transcript.created_at >= start_date
    ).all()
    
    live_sessions = LiveSession.query.filter(
        LiveSession.user_id == user_id,
        LiveSession.created_at >= start_date
    ).all()
    
    summaries = Summary.query.filter(
        Summary.user_id == user_id,
        Summary.created_at >= start_date
    ).all()
    
    tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.created_at >= start_date
    ).all()
    
    sentiments = SentimentAnalysis.query.filter(
        SentimentAnalysis.user_id == user_id,
        SentimentAnalysis.created_at >= start_date
    ).all()
    
    # Daily activity
    daily_activity = {}
    for i in range(days + 1):
        date = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
        daily_activity[date] = {'transcripts': 0, 'live_sessions': 0, 'summaries': 0, 'tasks': 0}
    
    for t in transcripts:
        date = t.created_at.strftime('%Y-%m-%d')
        if date in daily_activity:
            daily_activity[date]['transcripts'] += 1
    
    for l in live_sessions:
        date = l.created_at.strftime('%Y-%m-%d')
        if date in daily_activity:
            daily_activity[date]['live_sessions'] += 1
    
    for s in summaries:
        date = s.created_at.strftime('%Y-%m-%d')
        if date in daily_activity:
            daily_activity[date]['summaries'] += 1
    
    for t in tasks:
        date = t.created_at.strftime('%Y-%m-%d')
        if date in daily_activity:
            daily_activity[date]['tasks'] += 1
    
    # Sentiment distribution
    sentiment_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
    for s in sentiments:
        sentiment = s.sentiment.lower()
        if sentiment in sentiment_counts:
            sentiment_counts[sentiment] += 1
    
    return jsonify({
        "success": True,
        "analytics": {
            "totals": {
                "transcripts": len(transcripts),
                "live_sessions": len(live_sessions),
                "summaries": len(summaries),
                "tasks": len(tasks),
                "sentiments": len(sentiments)
            },
            "daily_activity": daily_activity,
            "sentiment_distribution": sentiment_counts,
            "task_completion": {
                "pending": sum(1 for t in tasks if t.status == 'pending'),
                "completed": sum(1 for t in tasks if t.status == 'completed')
            }
        }
    })

# ========== FILES API ==========
@app.route("/api/files", methods=["GET"])
@api_login_required
def get_files():
    """Get all files for user"""
    user_id = session['user_id']
    
    transcripts = Transcript.query.filter_by(user_id=user_id).all()
    live_sessions = LiveSession.query.filter_by(user_id=user_id).all()
    summaries = Summary.query.filter_by(user_id=user_id).all()
    translations = Translation.query.filter_by(user_id=user_id).all()
    
    files = []
    
    for t in transcripts:
        language = 'en'
        if t.transcript_data and 'metadata' in t.transcript_data:
            language = t.transcript_data['metadata'].get('language', 'en')
        
        files.append({
            'id': f'transcript_{t.id}',
            'type': 'transcript',
            'name': t.title,
            'date': t.created_at.isoformat(),
            'size': t.file_size,
            'word_count': t.word_count,
            'speakers': t.speaker_count,
            'duration': t.duration,
            'language': language,
            'audio_key': t.audio_key,
            'transcript_key': t.transcript_key
        })
    
    for l in live_sessions:
        files.append({
            'id': f'live_{l.id}',
            'type': 'live_session',
            'name': l.session_name,
            'date': l.created_at.isoformat(),
            'duration': l.duration,
            'word_count': l.word_count,
            'speakers': l.speaker_count,
            'language': l.detected_language
        })
    
    for s in summaries:
        files.append({
            'id': f'summary_{s.id}',
            'type': 'summary',
            'name': s.title,
            'date': s.created_at.isoformat(),
            'summary_type': s.summary_type,
            'word_count': s.word_count
        })
    
    for t in translations:
        files.append({
            'id': f'translation_{t.id}',
            'type': 'translation',
            'name': f'Translation from {t.source_lang} to {t.target_lang}',
            'date': t.created_at.isoformat(),
            'source_lang': t.source_lang,
            'target_lang': t.target_lang,
            'confidence': t.confidence
        })
    
    files.sort(key=lambda x: x['date'], reverse=True)
    
    return jsonify({"success": True, "files": files})

# ========== HEALTH CHECK ==========
@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    try:
        db.session.execute('SELECT 1')
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return jsonify({
        "status": "healthy",
        "database": db_status,
        "cloud_storage": supabase_storage.enabled,
        "timestamp": datetime.utcnow().isoformat()
    })

# ========== ERROR HANDLERS ==========
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return jsonify({"success": False, "error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"success": False, "error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)