# 🎓 EduPortal — Sistema Escolar (Flask)

Sistema web de escola com três perfis de usuário: **administrador** (direção), **professor** e **aluno**.

> Projeto da disciplina de Segurança — Etapa 1. Este repositório contém **vulnerabilidades inseridas de propósito** para o exercício de auditoria cruzada. **Não use em produção.**

## Funcionalidades
- Login com e-mail e senha, três níveis de permissão.
- CRUD de usuários, turmas e disciplinas (admin).
- Matrícula de alunos em turmas.
- Lançamento de notas por bimestre (professor) e boletim com médias (aluno).
- Mural de avisos com comentários.

## Como rodar
```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
python app.py
```
Abra **http://127.0.0.1:5000**. O banco `eduportal.db` é criado sozinho na primeira execução, já com dados de exemplo.

## Contas de teste
| Perfil | E-mail | Senha |
|---|---|---|
| Administrador | admin@eduportal.com | admin123 |
| Professor | ricardo@eduportal.com | prof123 |
| Professor | fernanda@eduportal.com | prof123 |
| Aluno | ana@eduportal.com | aluno123 |
| Aluno | bruno@eduportal.com | aluno123 |

## Estrutura
```
app.py           rotas, login e regras de permissão
database.py      conexão SQLite, schema e dados de exemplo
templates/       telas (Jinja2)
static/style.css visual
```

## Tecnologias
Python 3 · Flask 3 · SQLite · Jinja2.
