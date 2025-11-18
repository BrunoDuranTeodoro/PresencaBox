from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from functools import wraps
import cv2
import os
import base64
import numpy as np
from datetime import datetime

import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
app.secret_key = "algum_segredo_muito_secreto"

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
    

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Se o usuário não estiver logado → volta pro login
        if "professor_id" not in session:
            return redirect(url_for("login_professor"))
        return f(*args, **kwargs)
    return decorated_function

# ===== Página Inicial (presença) =======
@app.route('/')
def index():
    return render_template('index.html')

# ===== Página de Cadastro ===============
@app.route('/cadastrar')
def cadastrar():
    return render_template('cadastro.html')

# ===== Página de Alunos ===============
@app.route('/professor/alunos')
@login_required
def professor_alunos():
    professor_id = session.get("professor_id")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Buscar turmas do professor
        cursor.execute("""
            SELECT id, nome 
            FROM turmas 
            WHERE professor_id = %s
            ORDER BY nome
        """, (professor_id,))
        turmas = cursor.fetchall()

        # Buscar alunos dessas turmas
        cursor.execute("""
            SELECT a.id, a.nome, a.data_cadastro, t.nome AS turma
            FROM alunos a
            JOIN turmas t ON a.turma_id = t.id
            WHERE t.professor_id = %s
            ORDER BY t.nome, a.nome
        """, (professor_id,))
        alunos = cursor.fetchall()

        cursor.execute("SELECT nome FROM professores WHERE id = %s", (professor_id,))
        prof = cursor.fetchone()

        cursor.close()
        conn.close()

        return render_template(
            "Professor/meusAlunos.html",
            nome=prof["nome"],
            turmas=turmas,
            alunos=alunos,
            hoje=datetime.now(),
            current_year=datetime.now().year
        )

    except Exception as e:
        print("Erro:", e)
        return "Erro interno ao carregar alunos", 500

# ===== Página de Relatorios ===============
@app.route('/professor/relatorios')
def professor_relatorios():
    return render_template('Professor/relatorios.html')

@app.route('/get_turmas', methods=['GET'])
def get_turmas():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM turmas ORDER BY nome")
        turmas = cursor.fetchall()  # [(1, "Turma A"), (2, "Turma B"), ...]
        cursor.close()
        conn.close()

        turmas_list = [{"id": t[0], "nome": t[1]} for t in turmas]
        return jsonify(turmas_list)
    except Error as e:
        print("Erro ao buscar turmas:", e)
        return jsonify([])  # vazio se der erro


# ====== LOGIN DO PROFESSOR ======
@app.route('/professor/login', methods=['GET', 'POST'])
def login_professor():
    if request.method == 'GET':
        return render_template('Professor/loginProfessor.html', year_text=datetime.now().year)

    # POST — processar login
    email = request.form.get("email")
    senha = request.form.get("senha")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM professores 
            WHERE email = %s AND senha = %s
        """, (email, senha))

        professor = cursor.fetchone()

        cursor.close()
        conn.close()

        if not professor:
            return render_template(
                "Professor/loginProfessor.html",
                erro="Email ou senha incorretos.",
                year_text=datetime.now().year
            )

        # Criar sessão
        session["professor_id"] = professor["id"]
        session["professor_nome"] = professor["nome"]

        # Atualizar último login
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE professores SET ultimo_login = NOW() WHERE id = %s", (professor["id"],))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for("dashboard_professor"))

    except Exception as e:
        print("Erro no login:", e)
        return render_template(
            "Professor/loginProfessor.html",
            erro="Erro no servidor. Tente novamente.",
            year_text=datetime.now().year
        )

@app.route('/professor/logout')
def logout_professor():
    session.clear()
    return redirect(url_for("login_professor"))


# ===== Página de Dashboard do Professor ==
@app.route('/professor/dashboard')
@login_required
def dashboard_professor():
    professor_id = session.get("professor_id")
    if not professor_id:
        return "Erro: sessão do professor não encontrada", 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM professores WHERE id = %s", (professor_id,))
    professor = cursor.fetchone()
    cursor.close()
    conn.close()

    if not professor:
        return f"Erro: professor com id {professor_id} não encontrado", 404

    return render_template(
        "Professor/dashboardProfessor.html",
        professor=professor,                         # envia objeto completo
        nome=professor["nome"],                      # envia somente o nome
        turmas=[],
        hoje=datetime.now(),
        current_year=datetime.now().year
    )

# ===== Página de Perfil do Professor =====
@app.route('/professor/perfil')
@login_required
def perfil_professor():
    professor_id = session.get("professor_id")
    if not professor_id:
        return redirect(url_for("login_professor"))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Pega dados do professor
        cursor.execute("SELECT * FROM professores WHERE id = %s", (professor_id,))
        professor = cursor.fetchone()
        if not professor:
            return "Professor não encontrado", 404

        # Pega turmas do professor
        cursor.execute("SELECT nome FROM turmas WHERE professor_id = %s", (professor_id,))
        turmas = [t["nome"] for t in cursor.fetchall()]

        professor["turmas"] = turmas

        cursor.close()
        conn.close()

        # Formata datas para exibir no HTML
        professor["acesso"] = professor["data_acesso"].strftime("%d/%m/%Y") if professor["data_acesso"] else ""
        professor["ultimo_login"] = professor["ultimo_login"].strftime("%d/%m/%Y %H:%M") if professor["ultimo_login"] else ""

        return render_template(
            'Professor/perfilProfessor.html',
            professor=professor,
            current_year=datetime.now().year,
            hoje=datetime.now()
        )

    except Exception as e:
        print("Erro ao carregar perfil:", e)
        return "Erro interno", 500


# ===== Salvar novo rosto =====
@app.route('/salvar_cadastro', methods=['POST'])
def salvar_cadastro():
    data = request.json
    nome = data['nome']
    turma_id = data.get('turma_id') 
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

        cursor.execute("""
            INSERT INTO alunos (nome, turma_id, data_cadastro)
            VALUES (%s, %s, %s)
        """, (nome, turma_id, datetime.now()))

        conn.commit()
        cursor.close()
        conn.close()

    except Error as e:
        print("Erro ao inserir no banco:", e)
        return jsonify({'status': 'erro', 'mensagem': 'Erro ao salvar no banco.'})

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