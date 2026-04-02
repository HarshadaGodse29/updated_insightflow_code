import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
from models import *

def ensure_instance_dir():
    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    
    os.makedirs(instance_dir, exist_ok=True)
    
    try:
        import stat
        os.chmod(instance_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
    except:
        pass
    
    db_file = os.path.join(instance_dir, 'insightflow.db')
    if not os.path.exists(db_file):
        open(db_file, 'w').close()
        print(f"Created database file: {db_file}")
    
    return instance_dir

def init_db():
    with app.app_context():
        instance_dir = ensure_instance_dir()
        print(f"Instance directory: {instance_dir}")
        
        print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        print("Dropping all tables...")
        db.drop_all()
        print("Dropped all existing tables")
        
        print("Creating all tables...")
        db.create_all()
        print("Created all tables")
        
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@insightflow.com',
                full_name='Admin User',
                job_title='System Administrator',
                department='IT'
            )
            admin.set_password('password123')
            db.session.add(admin)
            db.session.flush()
            print("Created admin user")
        
        settings = UserSettings.query.filter_by(user_id=admin.id).first()
        if not settings:
            settings = UserSettings(
                user_id=admin.id,
                email_notifications=True,
                desktop_notifications=True,
                theme='dark',
                sidebar_collapsed=False
            )
            db.session.add(settings)
            print("Created user settings")
        
        db.session.commit()
        
        print("\n" + "="*50)
        print("Database initialized successfully!")
        print("="*50)
        print(f"Database location: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("Admin user: admin@insightflow.com / password123")
        print("="*50)

def add_sample_data():
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        
        if not admin:
            print("Admin user not found. Run without --sample first.")
            return
        
        print("Adding sample data...")
        
        if Transcript.query.filter_by(user_id=admin.id).first():
            print("Sample data already exists. Skipping.")
            return
        
        transcript = Transcript(
            user_id=admin.id,
            filename='team_meeting_q4.mp3',
            title='Team Meeting - Q4 Planning',
            duration=1860,
            word_count=3245,
            speaker_count=4,
            file_size=15.2 * 1024 * 1024,
            audio_key='audio/1/sample_audio.mp3',
            transcript_key='transcripts/1/sample_transcript.json',
            transcript_data={
                'segments': [
                    {'speaker': 'Speaker A', 'text': "Let's discuss Q4 goals and objectives."},
                    {'speaker': 'Speaker B', 'text': 'I think we should focus on increasing market share.'},
                    {'speaker': 'Speaker C', 'text': 'The budget allocation needs review.'},
                    {'speaker': 'Speaker A', 'text': 'Agreed. Let\'s schedule a follow-up.'}
                ]
            }
        )
        db.session.add(transcript)
        db.session.flush()
        print("Added sample transcript")
        
        summary = Summary(
            user_id=admin.id,
            transcript_id=transcript.id,
            title='Q4 Planning Meeting Summary',
            content='''EXECUTIVE SUMMARY:
The team discussed Q4 goals focusing on market share increase.

KEY DECISIONS:
- Target 15% market share increase
- Review budget allocation
- Schedule finance meeting

ACTION ITEMS:
- Prepare budget report - John
- Schedule follow-up - Sarah''',
            summary_type='executive',
            length='medium',
            word_count=85
        )
        db.session.add(summary)
        print("Added sample summary")
        
        tasks = [
            Task(
                user_id=admin.id,
                transcript_id=transcript.id,
                title='Prepare Q4 budget report',
                assignee='John Smith',
                deadline=datetime.now() + timedelta(days=7),
                priority='high',
                status='pending'
            ),
            Task(
                user_id=admin.id,
                transcript_id=transcript.id,
                title='Schedule finance meeting',
                assignee='Sarah Johnson',
                deadline=datetime.now() + timedelta(days=3),
                priority='medium',
                status='pending'
            )
        ]
        db.session.add_all(tasks)
        print("Added sample tasks")
        
        db.session.commit()
        print("\nSample data added successfully!")

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Database Migration Tool")
    print("="*50)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--sample':
        add_sample_data()
    else:
        init_db()
        print("\nRun with --sample to add test data: python migrate.py --sample")