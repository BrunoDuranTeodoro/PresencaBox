from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from functools import wraps
import cv2
import os
import base64
import numpy as np
from datetime import datetime, timedelta

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
    return render_template('index.html', current_year=datetime.now().year)

# ===== Página de Cadastro ===============
@app.route('/cadastrar')
@login_required 
def cadastrar():
    return render_template('cadastro.html')

# ===== Página de Alunos ===============
@app.route('/professor/alunos')
@login_required
def professor_alunos():
    professor_id = session.get("professor_id")

    # Recebendo filtros da URL
    filtro_turma = request.args.get("turma")
    busca_nome = request.args.get("busca")
    ordem = request.args.get("ordem", "asc")  # asc ou desc

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

        # Montar query dinamicamente
        query = """
            SELECT a.id, a.nome, a.data_cadastro, t.nome AS turma
            FROM alunos a
            JOIN turmas t ON a.turma_id = t.id
            WHERE t.professor_id = %s
        """
        params = [professor_id]

        # Filtro por turma
        if filtro_turma and filtro_turma != "todas":
            query += " AND t.id = %s"
            params.append(filtro_turma)

        # Filtro por nome (busca)
        if busca_nome:
            query += " AND a.nome LIKE %s"
            params.append(f"%{busca_nome}%")

        # Ordenação
        if ordem == "desc":
            query += " ORDER BY a.nome DESC"
        else:
            query += " ORDER BY a.nome ASC"

        cursor.execute(query, params)
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
            filtro_turma=filtro_turma,
            busca_nome=busca_nome,
            ordem=ordem,
            hoje=datetime.now(),
            current_year=datetime.now().year
        )

    except Exception as e:
        print("Erro:", e)
        return "Erro interno ao carregar alunos", 500


# ===== Página de Relatorios ===============
@app.route('/professor/relatorios')
@login_required
def professor_relatorios():
    professor_id = session.get("professor_id")

    # Filtros da URL
    data_str = request.args.get("data")
    if not data_str:
        data_ref = datetime.now().date()
        data_str = data_ref.strftime("%Y-%m-%d")
    else:
        data_ref = datetime.strptime(data_str, "%Y-%m-%d").date()

    filtro_turma = request.args.get("turma", "todas")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Turmas do professor (para o select)
        cursor.execute("""
            SELECT id, nome
            FROM turmas
            WHERE professor_id = %s
            ORDER BY nome
        """, (professor_id,))
        turmas = cursor.fetchall()

        # Relatório de presenças
        query = """
            SELECT 
                p.id,
                p.data_hora,
                COALESCE(a.nome, p.aluno_nome) AS aluno_nome,
                t.nome AS turma_nome
            FROM presencas p
            LEFT JOIN alunos a ON p.aluno_id = a.id
            LEFT JOIN turmas t ON a.turma_id = t.id
            WHERE t.professor_id = %s
              AND DATE(p.data_hora) = %s
        """
        params = [professor_id, data_ref]

        if filtro_turma != "todas" and filtro_turma:
            query += " AND t.id = %s"
            params.append(filtro_turma)

        query += " ORDER BY p.data_hora DESC"

        cursor.execute(query, params)
        presencas = cursor.fetchall()

        # Número total de presenças no dia (já filtrado)
        total_presencas = len(presencas)

        cursor.close()
        conn.close()

    except Exception as e:
        print("Erro ao carregar relatórios:", e)
        return "Erro interno ao carregar relatórios", 500

    return render_template(
        "Professor/relatorios.html",
        nome=session.get("professor_nome"),
        turmas=turmas,
        presencas=presencas,
        filtro_turma=filtro_turma,
        data_selecionada=data_str,
        total_presencas=total_presencas,
        hoje=datetime.now(),
        current_year=datetime.now().year
    )

@app.route('/get_turmas', methods=['GET'])
@login_required
def get_turmas():
    try:
        professor_id = session.get("professor_id")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nome 
            FROM turmas 
            WHERE professor_id = %s
            ORDER BY nome
        """, (professor_id,))
        turmas = cursor.fetchall()
        cursor.close()
        conn.close()

        turmas_list = [{"id": t[0], "nome": t[1]} for t in turmas]
        return jsonify(turmas_list)
    except Error as e:
        print("Erro ao buscar turmas:", e)
        return jsonify([])

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

    hoje = datetime.now()
    hoje_date = hoje.date()
    start_date = hoje_date - timedelta(days=6)  # últimos 7 dias (inclui hoje)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1) Dados do professor
        cursor.execute("SELECT * FROM professores WHERE id = %s", (professor_id,))
        professor = cursor.fetchone()

        # 2) Quantidade de turmas
        cursor.execute("""
            SELECT COUNT(*) AS total_turmas
            FROM turmas
            WHERE professor_id = %s
        """, (professor_id,))
        total_turmas = cursor.fetchone()["total_turmas"]

        # 3) Quantidade de alunos
        cursor.execute("""
            SELECT COUNT(*) AS total_alunos
            FROM alunos a
            JOIN turmas t ON a.turma_id = t.id
            WHERE t.professor_id = %s
        """, (professor_id,))
        total_alunos = cursor.fetchone()["total_alunos"]

        # 4) Presenças hoje
        cursor.execute("""
            SELECT COUNT(*) AS presencas_hoje
            FROM presencas p
            JOIN alunos a ON p.aluno_id = a.id
            JOIN turmas t ON a.turma_id = t.id
            WHERE t.professor_id = %s
              AND DATE(p.data_hora) = %s
        """, (professor_id, hoje_date))
        presencas_hoje = cursor.fetchone()["presencas_hoje"]

        # 5) Presenças no mês
        cursor.execute("""
            SELECT COUNT(*) AS presencas_mes
            FROM presencas p
            JOIN alunos a ON p.aluno_id = a.id
            JOIN turmas t ON a.turma_id = t.id
            WHERE t.professor_id = %s
              AND YEAR(p.data_hora) = %s
              AND MONTH(p.data_hora) = %s
        """, (professor_id, hoje_date.year, hoje_date.month))
        presencas_mes = cursor.fetchone()["presencas_mes"]

        # 6) Alunos sem presença hoje
        cursor.execute("""
            SELECT COUNT(*) AS alunos_sem_presenca_hoje
            FROM alunos a
            JOIN turmas t ON a.turma_id = t.id
            WHERE t.professor_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM presencas p
                  WHERE p.aluno_id = a.id
                    AND DATE(p.data_hora) = %s
              )
        """, (professor_id, hoje_date))
        alunos_sem_presenca_hoje = cursor.fetchone()["alunos_sem_presenca_hoje"]

        # 7) Dados para o gráfico - presenças por dia e turma (últimos 7 dias)
        cursor.execute("""
            SELECT 
                DATE(p.data_hora) AS dia,
                t.nome AS turma_nome,
                COUNT(*) AS total
            FROM presencas p
            JOIN alunos a ON p.aluno_id = a.id
            JOIN turmas t ON a.turma_id = t.id
            WHERE t.professor_id = %s
              AND DATE(p.data_hora) BETWEEN %s AND %s
            GROUP BY dia, turma_nome
            ORDER BY dia, turma_nome
        """, (professor_id, start_date, hoje_date))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

    except Exception as e:
        print("Erro no dashboard:", e)
        return "Erro interno ao carregar dashboard", 500

    if not professor:
        return f"Erro: professor com id {professor_id} não encontrado", 404

    # Montar lista de dias (últimos 7 dias)
    dias = [start_date + timedelta(days=i) for i in range(7)]
    chart_labels = [d.strftime("%d/%m") for d in dias]

    # Montar estrutura: { "ADS A": [0, 2, 1, ...], "Turma X": [...] }
    chart_data = {}
    for row in rows:
        dia = row["dia"]      # date
        turma = row["turma_nome"]
        total = row["total"]

        if turma not in chart_data:
            chart_data[turma] = [0] * len(dias)

        idx = (dia - start_date).days
        if 0 <= idx < len(dias):
            chart_data[turma][idx] = total

    return render_template(
        "Professor/dashboardProfessor.html",
        professor=professor,
        nome=professor["nome"],
        hoje=hoje,
        current_year=hoje.year,
        total_turmas=total_turmas,
        total_alunos=total_alunos,
        presencas_hoje=presencas_hoje,
        presencas_mes=presencas_mes,
        alunos_sem_presenca_hoje=alunos_sem_presenca_hoje,
        chart_labels=chart_labels,
        chart_data=chart_data
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
@login_required
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
    if conf < 80:  # Ajuste conforme testes
        nome_reconhecido = nomes_dict[label]
        agora = datetime.now()

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Tenta encontrar o aluno pelo nome (pega o primeiro que achar)
            cursor.execute(
                "SELECT id FROM alunos WHERE nome = %s LIMIT 1",
                (nome_reconhecido,)
            )
            row = cursor.fetchone()
            aluno_id = row[0] if row else None

            # Insere a presença
            cursor.execute("""
                INSERT INTO presencas (aluno_id, aluno_nome, data_hora)
                VALUES (%s, %s, %s)
            """, (aluno_id, nome_reconhecido, agora))

            conn.commit()
            cursor.close()
            conn.close()

        except Error as e:
            print("Erro ao registrar presença no banco:", e)
            return jsonify({
                'status': 'erro',
                'mensagem': f'Presença reconhecida para {nome_reconhecido}, mas houve erro ao salvar no banco.'
            })

        hora = agora.strftime("%H:%M:%S")
        return jsonify({
            'status': 'ok',
            'mensagem': f'Presença registrada para {nome_reconhecido} às {hora}.'
        })
    else:
        return jsonify({'status': 'erro', 'mensagem': 'Rosto não encontrado.'})

if __name__ == '__main__':
    app.run('0.0.0.0',debug=True)