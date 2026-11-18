import hashlib
import sqlite3
from pathlib import Path

from flask import g

BANCO = Path(__file__).parent / "eduportal.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    senha VARCHAR(64) NOT NULL,
    perfil VARCHAR(10) NOT NULL CHECK (perfil IN ('admin', 'professor', 'aluno')),
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS turmas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(50) NOT NULL,
    ano INTEGER NOT NULL,
    turno VARCHAR(10) NOT NULL
);

CREATE TABLE IF NOT EXISTS disciplinas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(80) NOT NULL,
    carga_horaria INTEGER NOT NULL,
    turma_id INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
    professor_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS matriculas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    turma_id INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
    data_matricula DATE DEFAULT CURRENT_DATE,
    UNIQUE (aluno_id, turma_id)
);

CREATE TABLE IF NOT EXISTS notas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    disciplina_id INTEGER NOT NULL REFERENCES disciplinas(id) ON DELETE CASCADE,
    bimestre INTEGER NOT NULL CHECK (bimestre BETWEEN 1 AND 4),
    valor DECIMAL(4, 2) NOT NULL CHECK (valor BETWEEN 0 AND 10),
    UNIQUE (aluno_id, disciplina_id, bimestre)
);

CREATE TABLE IF NOT EXISTS avisos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    autor_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    titulo VARCHAR(120) NOT NULL,
    conteudo TEXT NOT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comentarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aviso_id INTEGER NOT NULL REFERENCES avisos(id) ON DELETE CASCADE,
    autor_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    texto TEXT NOT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def conectar():
    """Abre (uma vez por requisição) a conexão com o banco."""
    if "db" not in g:
        g.db = sqlite3.connect(BANCO)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def fechar(_erro=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def hash_senha(senha):
    return hashlib.md5(senha.encode()).hexdigest()


def criar_banco():
    """Cria as tabelas e alguns dados de exemplo (só na primeira vez)."""
    novo = not BANCO.exists()
    db = sqlite3.connect(BANCO)
    db.executescript(SCHEMA)
    if novo:
        popular(db)
    db.commit()
    db.close()


def popular(db):
    usuarios = [
        ("Diretora Helena Prado", "admin@eduportal.com", "admin123", "admin"),
        ("Prof. Ricardo Alves", "ricardo@eduportal.com", "prof123", "professor"),
        ("Prof.ª Fernanda Lima", "fernanda@eduportal.com", "prof123", "professor"),
        ("Ana Beatriz Souza", "ana@eduportal.com", "aluno123", "aluno"),
        ("Bruno Henrique Costa", "bruno@eduportal.com", "aluno123", "aluno"),
        ("Carla Menezes", "carla@eduportal.com", "aluno123", "aluno"),
        ("Diego Martins", "diego@eduportal.com", "aluno123", "aluno"),
    ]
    for nome, email, senha, perfil in usuarios:
        db.execute(
            "INSERT INTO usuarios (nome, email, senha, perfil) VALUES (?, ?, ?, ?)",
            (nome, email, hash_senha(senha), perfil),
        )

    db.execute("INSERT INTO turmas (nome, ano, turno) VALUES ('1º Ano A', 2026, 'Manhã')")
    db.execute("INSERT INTO turmas (nome, ano, turno) VALUES ('2º Ano B', 2026, 'Tarde')")

    disciplinas = [
        ("Matemática", 80, 1, 2), ("Português", 80, 1, 3),
        ("História", 60, 2, 3), ("Física", 60, 2, 2),
    ]
    db.executemany(
        "INSERT INTO disciplinas (nome, carga_horaria, turma_id, professor_id) VALUES (?, ?, ?, ?)",
        disciplinas,
    )

    for aluno_id, turma_id in [(4, 1), (5, 1), (6, 2), (7, 2)]:
        db.execute("INSERT INTO matriculas (aluno_id, turma_id) VALUES (?, ?)", (aluno_id, turma_id))

    notas = [
        (4, 1, 1, 8.5), (4, 1, 2, 9.0), (4, 2, 1, 7.0), (4, 2, 2, 7.5),
        (5, 1, 1, 6.0), (5, 1, 2, 5.5), (5, 2, 1, 8.0), (5, 2, 2, 9.0),
        (6, 3, 1, 9.5), (6, 4, 1, 4.0), (7, 3, 1, 7.0), (7, 4, 1, 6.5),
    ]
    db.executemany(
        "INSERT INTO notas (aluno_id, disciplina_id, bimestre, valor) VALUES (?, ?, ?, ?)", notas
    )

    db.execute(
        "INSERT INTO avisos (autor_id, titulo, conteudo) VALUES (1, ?, ?)",
        ("Bem-vindos ao EduPortal!", "A partir de agora notas e avisos ficam todos por aqui.\nQualquer dúvida, procurem a secretaria."),
    )
    db.execute(
        "INSERT INTO avisos (autor_id, titulo, conteudo) VALUES (2, ?, ?)",
        ("Prova de Matemática", "A prova do 2º bimestre será na próxima sexta.\nConteúdo: funções do 1º grau."),
    )
    db.execute(
        "INSERT INTO comentarios (aviso_id, autor_id, texto) VALUES (2, 4, 'Vai ter consulta ao caderno, professor?')"
    )
