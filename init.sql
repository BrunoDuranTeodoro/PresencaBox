CREATE TABLE IF NOT EXISTS professores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    senha VARCHAR(255) NOT NULL,  
    email VARCHAR(255) NOT NULL,
    cargo VARCHAR(100),
    unidade VARCHAR(255),
    telefone VARCHAR(20),
    data_acesso DATE,
    ultimo_login DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS turmas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    professor_id INT,
    FOREIGN KEY (professor_id) REFERENCES professores(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alunos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    turma_id INT NOT NULL,
    data_cadastro DATETIME,

    FOREIGN KEY (turma_id) REFERENCES turmas(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ================================
-- INSERTS DE TESTE
-- ================================

INSERT INTO professores 
(nome, senha, email, cargo, unidade, telefone, data_acesso, ultimo_login)
VALUES 
(
    'Professor Teste',
    'senha123',
    'professor@senai.com',
    'Instrutor Tecnico I',
    'SENAI-SP Unidade Industrial',
    '(11)90000-0000',
    '2020-01-10',
    NOW()
);

INSERT INTO turmas (nome, professor_id)
VALUES 
(
    'ADS A',
    LAST_INSERT_ID()
);

INSERT INTO alunos (nome, turma_id, data_cadastro)
VALUES
('João da Silva', 1, NOW()),
('Maria Pereira', 1, NOW());
