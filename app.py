# app.py
from flask import Flask, render_template, request, redirect, url_for, session
from flask_pymongo import PyMongo
from flask_socketio import SocketIO
import uuid

app = Flask(__name__)
app.config['MONGO_URI'] = 'mongodb+srv://testonlytest7:76HdaZzXXgSqb4HN@learnapi.ftvefwf.mongodb.net/db_quizz_app?retryWrites=true&w=majority'
app.secret_key = 'your_secret_key'
mongo = PyMongo(app)
socketio = SocketIO(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        password = request.form['password']
        country = request.form['country']

        user_signup = mongo.db.userSignup
        user_signup.insert_one({'FULLNAME': fullname, 'USERNAME': username, 'PASSWORD': password, 'COUNTRY': country})
        
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user_data = mongo.db.userSignup.count_documents({'USERNAME': username, 'PASSWORD': password})
        if user_data > 0:
            session['username'] = username
            return redirect(url_for('menu'))
        else:
            error = "Wrong Username or Password!"
            return render_template('login.html', error=error)

    return render_template('login.html')

@app.route('/menu', methods=['GET', 'POST'])
def menu():
    if 'username' in session:
        if request.method == 'POST':
            role = request.form.get('role')
            if role == 'quiz_master':
                return redirect(url_for('create_room'))
            elif role == 'quiz_participant':
                return redirect(url_for('join_room'))

        return render_template('menu.html')

    return redirect(url_for('login'))

@app.route('/create_room', methods=['GET', 'POST'])
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
            'questions': []
        }

        for i in range(len(questions)):
            question = {
                'question_text': questions[i],
                'options': options[i],
                'correct_answer': correct_answers[i]
            }
            room_data['questions'].append(question)

        # Add participants key to room_data
        room_data['participants'] = []

        mongo.db.quiz_rooms.insert_one(room_data)

        return redirect(url_for('waiting_room', room_number=room_number))

    return render_template('create_room.html', room_number=room_number)


@app.route('/waiting_room/<room_number>', methods=['GET', 'POST'])
def waiting_room(room_number):
    print(f"Waiting room accessed. room_number: {room_number}")
    if 'username' in session:
        # Use count_documents to check if the room exists
        room_count = mongo.db.quiz_rooms.count_documents({'room_number': room_number})

        if room_count > 0:
            room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})

            is_quiz_master = session['username'] == room_data['quiz_master']

            print(f"Room {room_number} found. is_quiz_master: {is_quiz_master}")

            if request.method == 'POST' and is_quiz_master:
                socketio.emit('quiz_started', room=room_number)  # Notify clients that the quiz has started
                return redirect(url_for('quiz_room', room_number=room_number))
            elif request.method == 'POST':
                # Participant tried to start the quiz, show an error or redirect to a different page
                error = "Only the quiz master can start the quiz."
                return render_template('waiting_room.html', room_number=room_number, is_quiz_master=is_quiz_master, participants=participants, error=error)

            # Check if 'participants' key exists in room_data
            participants = room_data.get('participants', [])

            return render_template('waiting_room.html', room_number=room_number, is_quiz_master=is_quiz_master, participants=participants)

        else:
            print(f"Room {room_number} not found. room_count: {room_count}")
            return render_template('room_not_found.html')  # Create a room_not_found.html template

    return redirect(url_for('login'))

@app.route('/waiting_room_user/<room_number>', methods=['GET', 'POST'])
def waiting_room_user(room_number):
    if 'username' in session:
        room_count = mongo.db.quiz_rooms.count_documents({'room_number': room_number})

        if room_count > 0:
            room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})

            is_quiz_master = session['username'] == room_data['quiz_master']

            if request.method == 'POST' and is_quiz_master:
                socketio.emit('quiz_started', room=room_number)
                return redirect(url_for('quiz_room', room_number=room_number))
            elif request.method == 'POST':
                error = "Only the quiz master can start the quiz."
                return render_template('waiting_room_user.html', room_number=room_number, is_quiz_master=is_quiz_master, participants=participants, error=error)
            
            participants = room_data.get('participants', [])

            return render_template('waiting_room_user.html', room_number=room_number, is_quiz_master=is_quiz_master, participants=participants)
        
        else:
            return render_template('room_not_found.html')
        
    return redirect(url_for('login'))






@app.route('/start_quiz/<int:room_number>', methods=['POST'])
def start_quiz(room_number):
    socketio.emit('quiz_started', room=room_number)
    return redirect(url_for('quiz_room', room_number=room_number))

@app.route('/join_room', methods=['GET', 'POST'])
def join_room():
    if 'username' in session:
        if request.method == 'POST':
            room_number = request.form['room_number']
            room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})

            if room_data:
                participants = room_data.get('participants', [])
                participants.append(session['username'])

                mongo.db.quiz_rooms.update_one(
                    {'room_number': room_number},
                    {'$set': {'participants': participants}}
                )

                return redirect(url_for('waiting_room_user', room_number=room_number))
            else:
                error = "Invalid Room Number. Please try again."
                return render_template('join_room.html', error=error)

        return render_template('join_room.html')

    return redirect(url_for('login'))

@app.route('/quiz_room/<int:room_number>')
def quiz_room(room_number):
    if 'username' in session:
        room_data = mongo.db.quiz_rooms.find_one({'room_number': room_number})

        if room_data:
            quiz_master = room_data['quiz_master']
            return render_template('quiz_room.html', room_number=room_number, quiz_master=quiz_master)

    return redirect(url_for('login'))

if __name__ == '__main__':
    socketio.run(app, debug=True)
