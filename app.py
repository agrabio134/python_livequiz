from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session
from flask_pymongo import PyMongo
from flask_socketio import SocketIO
import uuid
import secrets
import jwt
from datetime import datetime, timedelta
from flask import jsonify


app = Flask(__name__)
app.config['MONGO_URI'] = 'mongodb+srv://testonlytest7:76HdaZzXXgSqb4HN@learnapi.ftvefwf.mongodb.net/db_quizz_app?retryWrites=true&w=majority'
app.secret_key = 'your_secret_key'
mongo = PyMongo(app)
socketio = SocketIO(app)

secret_key = secrets.token_hex(32)
app.config['JWT_SECRET_KEY'] = secret_key



def generate_jwt_token(username):
    payload = {
        'exp': datetime.utcnow() + timedelta(days=1),
        'iat': datetime.utcnow(),
        'sub': username
    }
    token = jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')
    return token
    

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        password = request.form['password']
        user_signup = mongo.db.userSignup
        user_signup.insert_one({'FULLNAME': fullname, 'USERNAME': username, 'PASSWORD': password})
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    # return redirect(url_for('login'))
    return redirect(url_for('login'))




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = mongo.db.userSignup.find_one({'USERNAME': username, 'PASSWORD': password})

        if user_data:
            token = generate_jwt_token(username)
            session['username'] = username  # Set the username in the session
            response = redirect(url_for('menu'))
            response.set_cookie('token', token)
            return response
        else:
            error = "Wrong Username or Password!"
            return render_template('login.html', error=error)

    return render_template('login.html')

@app.route('/menu', methods=['GET', 'POST'])
@login_required
def menu():
    if request.method == 'POST':
        role = request.form.get('role')
        if role == 'quiz_master':
            return redirect(url_for('create_room'))
        elif role == 'quiz_participant':
            return redirect(url_for('join_room'))

    return render_template('menu.html')

@app.route('/kick_user/<room_number>/<username>', methods=['POST'])
@login_required
def kick_user(room_number, username):
    room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})
    quiz_master = room_data['quiz_master']

    if session['username'] == quiz_master:
        participants = room_data.get('participants', [])
        if username in participants:
            participants.remove(username)

            # Update the room with the modified participants list
            mongo.db.quiz_rooms.update_one(
                {'room_number': room_number},
                {'$set': {'participants': participants}}
            )

            # Notify the kicked user via SocketIO
            socketio.emit('user_kicked', {'message': 'You have been kicked from the room.'}, room=username)

            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'User not found in the room.'})
    else:
        return jsonify({'success': False, 'message': 'Only the quiz master can kick users.'})

@app.route('/create_room', methods=['GET', 'POST'])
@login_required
def create_room():
    room_number = None

    if request.method == 'POST':
        room_number = str(uuid.uuid4().int)[:6]
        quiz_name = request.form['quiz_name']
        categories = request.form['categories']
        quiz_difficulty = request.form['quiz_difficulty']
        questions = request.form.getlist('questions[]')
        options = [request.form.getlist(f'options[{i}][]') for i in range(len(questions))]
        correct_answers = [int(request.form[f'correct_answer[{i}]']) for i in range(len(questions))]

        room_data = {
            'room_number': room_number,
            'quiz_name': quiz_name,
            'categories': categories,
            'quiz_difficulty': quiz_difficulty,
            'quiz_master': session.get('username'),
            'questions': [],
            'participants': [],
            'is_started': False  # Add the flag to indicate whether the quiz has started
        }

        for i in range(len(questions)):
            question = {
                'question_text': questions[i],
                'options': options[i],
                'correct_answer': correct_answers[i]
            }
            room_data['questions'].append(question)

        mongo.db.quiz_rooms.insert_one(room_data)

        return redirect(url_for('waiting_room', room_number=room_number))

    return render_template('create_room.html', room_number=room_number)


@app.route('/waiting_room/<room_number>', methods=['GET', 'POST'])
@login_required
def waiting_room(room_number):
    print(f"Waiting room accessed. room_number: {room_number}")
    room_count = mongo.db.quiz_rooms.count_documents({'room_number': room_number})

    if room_count > 0:
        room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})
        is_quiz_master = session['username'] == room_data['quiz_master']

        print(f"Room {room_number} found. is_quiz_master: {is_quiz_master}")

        if request.method == 'POST' and is_quiz_master:
            socketio.emit('quiz_started', room=room_number)
            return redirect(url_for('quiz_room', room_number=room_number))
        elif request.method == 'POST':
            error = "Only the quiz master can start the quiz."
            return render_template('waiting_room.html', room_number=room_number, is_quiz_master=is_quiz_master, participants=participants, error=error)

        participants = room_data.get('participants', [])
        return render_template('waiting_room.html', room_number=room_number, is_quiz_master=is_quiz_master, participants=participants)

    else:
        print(f"Room {room_number} not found. room_count: {room_count}")
        return render_template('room_not_found.html')

@app.route('/waiting_room_user/<room_number>', methods=['GET', 'POST'])
@login_required
def waiting_room_user(room_number):
    room_count = mongo.db.quiz_rooms.count_documents({'room_number': room_number})

    if room_count > 0:
        room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})
        is_quiz_master = session['username'] == room_data['quiz_master']

        if request.method == 'POST' and is_quiz_master:
            socketio.emit('quiz_started', room=room_number)
            return redirect(url_for('quiz_room', room_number=room_number))
        elif request.method == 'POST':
            error = "Only the quiz master can start the quiz."
            return render_template('waiting_room_user.html', room_number=room_number, is_quiz_master=is_quiz_master, participants=room_data.get('participants', []), error=error)
        
        participants = room_data.get('participants', [])
        return render_template('waiting_room_user.html', room_number=room_number, is_quiz_master=is_quiz_master, participants=participants)
    
    else:
        return render_template('room_not_found.html')
    
@app.route('/check_if_quiz_started/<room_number>')
def check_if_quiz_started(room_number):
    room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})
    is_started = room_data.get('is_started', False)
    return jsonify({'is_started': is_started})

@app.route('/get_participants/<room_number>')
def get_participants(room_number):
    room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})
    participants = room_data.get('participants', [])
    return jsonify({'participants': participants})

@app.route('/start_quiz/<room_number>', methods=['POST'])
@login_required
def start_quiz(room_number):
    room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})
    quiz_master = room_data['quiz_master']

    if session['username'] == quiz_master:
        # Update the flag to indicate that the quiz has started
        mongo.db.quiz_rooms.update_one(
            {'room_number': room_number},
            {'$set': {'is_started': True}}
        )

        socketio.emit('quiz_started', room=room_number)
        return redirect(url_for('quiz_room', room_number=room_number))
    else:
        return jsonify({'success': False, 'message': 'Only the quiz master can start the quiz.'})


@app.route('/join_room', methods=['GET', 'POST'])
@login_required
def join_room():
    if request.method == 'POST':
        room_number = request.form['room_number']
        room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})

        if room_data:
            participants = room_data.get('participants', [])
            new_participant = session['username']
            participants.append(new_participant)

            mongo.db.quiz_rooms.update_one(
                {'room_number': room_number},
                {'$set': {'participants': participants}}
            )

            # Emit event to notify other clients about the new participant
            socketio.emit('participant_joined', {'participant': new_participant, 'room_number': room_number}, room=room_number)

            return redirect(url_for('waiting_room_user', room_number=room_number))
        else:
            error = "Invalid Room Number. Please try again."
            return render_template('join_room.html', error=error)

    return render_template('join_room.html')


@app.route('/quiz_room/<room_number>')
@login_required
def quiz_room(room_number):
    room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})

    if room_data:
        quiz_master = room_data['quiz_master']
        return render_template('quiz_room.html', room_number=room_number, quiz_master=quiz_master)

    return redirect(url_for('login'))

if __name__ == '__main__':
    socketio.run(app, debug=True)
