from flask import Flask, render_template, request, jsonify, redirect, url_for
import cv2
import os
import base64
import numpy as np
from datetime import datetime

import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

# Pasta onde os rostos são salvos
FACES_DIR = "faces"
os.makedirs(FACES_DIR, exist_ok=True)

# ===== Conexao com o banco de dados =======
def get_db_connection():
    return mysql.connector.connect(
        host="db",          # nome do serviço no docker-compose
        user="root",
        password="root",
        database="faceapp"
    )

# ===== Página Inicial (presença) =======
@app.route('/')
def index():
    return render_template('index.html')

# ===== Página de Cadastro ===============
@app.route('/cadastrar')
def cadastrar():
    return render_template('cadastro.html')

# ===== Página de Login do Professor =====
@app.route('/professor/login')
def login_professor():
    return render_template('Professor/loginProfessor.html', datetime=datetime)

# ===== Página de Dashboard do Professor ==
@app.route('/professor/dashboard')
def dashboard_professor():
    # Passando datetime para o template
    return render_template(
        'Professor/dashboardProfessor.html',
        nome='Professor(a) Silva',
        current_year=datetime.now().year,
        hoje=datetime.now()
    )

# ===== Página de Perfil do Professor =====
@app.route('/professor/perfil')
def perfil_professor():
    professor = {
        "nome": "Professor(a) Silva",
        "cargo": "Instrutor Técnico I",
        "registro": "123456",
        "email": "professor.silva@senai.br",
        "unidade": "SENAI-SP Unidade Industrial",
        "telefone": "(11) 98765-4321",
        "acesso": "10/01/2020",
        "ultimo_login": "27/10/2025",
        "turmas": ["Téc. Elétrica A", "Téc. Mecânica B"]
    }

    return render_template(
        'Professor/perfilProfessor.html',
        professor=professor,
        current_year=datetime.now().year,
        hoje=datetime.now()
    )

# ===== Salvar novo rosto =====
@app.route('/salvar_cadastro', methods=['POST'])
def salvar_cadastro():
    data = request.json
    nome = data['nome']
    img_data = data['imagem']

    # Converter Base64 em imagem
    img_bytes = base64.b64decode(img_data.split(',')[1])
    np_img = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    # Detectar rosto e salvar apenas a região do rosto
    faces = face_cascade.detectMultiScale(frame, 1.3, 5)
    if len(faces) == 0:
        return jsonify({'status': 'erro', 'mensagem': 'Nenhum rosto detectado.'})

    for (x, y, w, h) in faces:
        rosto = frame[y:y+h, x:x+w]
        rosto = cv2.resize(rosto, (200, 200))
        cv2.imwrite(os.path.join(FACES_DIR, f"{nome}.jpg"), rosto)
        break

    # Salvar no banco
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (nome, data_cadastro) VALUES (%s, %s)", (nome, datetime.now()))
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        print("Erro ao inserir no banco:", e)

    return jsonify({'status': 'ok', 'mensagem': 'Rosto cadastrado com sucesso!'})


# ===== Registrar presença =====
@app.route('/capturar_presenca', methods=['POST'])
def capturar_presenca():
    data = request.json
    img_data = data['imagem']

    # Converter Base64 em imagem
    img_bytes = base64.b64decode(img_data.split(',')[1])
    np_img = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    # Detectar rosto
    faces = face_cascade.detectMultiScale(frame, 1.3, 5)
    if len(faces) == 0:
        return jsonify({'status': 'erro', 'mensagem': 'Nenhum rosto detectado.'})

    # Extrair o primeiro rosto
    for (x, y, w, h) in faces:
        rosto_capturado = frame[y:y+h, x:x+w]
        rosto_capturado = cv2.resize(rosto_capturado, (200, 200))
        rosto_capturado_gray = cv2.cvtColor(rosto_capturado, cv2.COLOR_BGR2GRAY)
        break

    # Preparar LBPH
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    faces_train = []
    labels_train = []
    nomes_dict = {}

    # Ler rostos cadastrados
    for i, arquivo in enumerate(os.listdir(FACES_DIR)):
        if arquivo.endswith(".jpg"):
            img_reg = cv2.imread(os.path.join(FACES_DIR, arquivo), cv2.IMREAD_GRAYSCALE)
            faces_train.append(img_reg)
            labels_train.append(i)
            nomes_dict[i] = arquivo.split('.')[0]

    if not faces_train:
        return jsonify({'status': 'erro', 'mensagem': 'Nenhum rosto cadastrado ainda.'})

    # Treinar o LBPH
    recognizer.train(faces_train, np.array(labels_train))

    # Prever
    label, conf = recognizer.predict(rosto_capturado_gray)

    # Limite de confiança (quanto menor, mais parecido)
    if conf < 80:  # Ajustável, testando você pode aumentar/decrementar
        hora = datetime.now().strftime("%H:%M:%S")
        return jsonify({
            'status': 'ok',
            'mensagem': f'Presença registrada para {nomes_dict[label]} às {hora}.'
        })
    else:
        return jsonify({'status': 'erro', 'mensagem': 'Rosto não encontrado.'})

if __name__ == '__main__':
    app.run('0.0.0.0',debug=True)