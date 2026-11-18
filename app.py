from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup, escape

from database import conectar, criar_banco, fechar, hash_senha

app = Flask(__name__)
app.secret_key = "escola123"
app.teardown_appcontext(fechar)

TURNOS = ["Manhã", "Tarde", "Noite"]
PERFIS = {"admin": "Administrador", "professor": "Professor", "aluno": "Aluno"}


# ---------------------------------------------------------------- utilidades

def login_obrigatorio(*perfis):
    """Exige login e, se informado, um dos perfis permitidos."""
    def decorador(view):
        @wraps(view)
        def envolvida(*args, **kwargs):
            if "usuario_id" not in session:
                flash("Faça login para continuar.", "erro")
                return redirect(url_for("login"))
            if perfis and session.get("perfil") not in perfis:
                abort(403)
            return view(*args, **kwargs)
        return envolvida
    return decorador


@app.template_filter("formatar")
def formatar(texto):
    """Mantém as quebras de linha que o usuário digitou."""
    return Markup(texto.replace("\n", "<br>"))


@app.context_processor
def dados_globais():
    return {"PERFIS": PERFIS}


@app.errorhandler(403)
def proibido(_erro):
    return render_template("erro.html", titulo="Acesso negado",
                           mensagem="Você não tem permissão para ver esta página."), 403


@app.errorhandler(404)
def nao_encontrado(_erro):
    return render_template("erro.html", titulo="Página não encontrada",
                           mensagem="O endereço que você tentou abrir não existe."), 404


# ---------------------------------------------------------------- login

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        db = conectar()
        consulta = f"SELECT * FROM usuarios WHERE email = '{email}' AND senha = '{hash_senha(senha)}'"
        usuario = db.execute(consulta).fetchone()
        if usuario:
            session["usuario_id"] = usuario["id"]
            session["nome"] = usuario["nome"]
            session["perfil"] = usuario["perfil"]
            flash(f"Olá, {usuario['nome'].split()[0]}!", "ok")
            return redirect(url_for("painel"))
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("login.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    """Cadastro público: contas criadas aqui são sempre de aluno."""
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        confirmar = request.form.get("confirmar", "")
        db = conectar()
        erro = None
        if not nome or not email or not senha:
            erro = "Preencha nome, e-mail e senha."
        elif len(senha) < 6:
            erro = "A senha precisa ter pelo menos 6 caracteres."
        elif senha != confirmar:
            erro = "As senhas não conferem."
        elif db.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone():
            erro = "Já existe uma conta com esse e-mail."
        if erro:
            flash(erro, "erro")
            return render_template("cadastro.html", nome=nome, email=email)
        db.execute("INSERT INTO usuarios (nome, email, senha, perfil) VALUES (?, ?, ?, 'aluno')",
                   (nome, email, hash_senha(senha)))
        db.commit()
        flash("Conta criada! Faça login para continuar.", "ok")
        return redirect(url_for("login"))
    return render_template("cadastro.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "ok")
    return redirect(url_for("login"))


@app.route("/")
@login_obrigatorio()
def painel():
    db = conectar()
    perfil = session["perfil"]
    dados = {}
    if perfil == "admin":
        for tabela in ("turmas", "disciplinas", "avisos"):
            dados[tabela] = db.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        dados["alunos"] = db.execute("SELECT COUNT(*) FROM usuarios WHERE perfil = 'aluno'").fetchone()[0]
        dados["professores"] = db.execute("SELECT COUNT(*) FROM usuarios WHERE perfil = 'professor'").fetchone()[0]
    elif perfil == "professor":
        dados["disciplinas"] = db.execute(
            "SELECT d.*, t.nome AS turma FROM disciplinas d JOIN turmas t ON t.id = d.turma_id "
            "WHERE d.professor_id = ? ORDER BY d.nome", (session["usuario_id"],)).fetchall()
    else:
        dados["turmas"] = db.execute(
            "SELECT t.* FROM turmas t JOIN matriculas m ON m.turma_id = t.id WHERE m.aluno_id = ?",
            (session["usuario_id"],)).fetchall()
    avisos = db.execute(
        "SELECT a.*, u.nome AS autor FROM avisos a JOIN usuarios u ON u.id = a.autor_id "
        "ORDER BY a.criado_em DESC LIMIT 3").fetchall()
    return render_template("painel.html", dados=dados, avisos=avisos)


@app.route("/perfil", methods=["GET", "POST"])
@login_obrigatorio()
def perfil():
    db = conectar()
    uid = session["usuario_id"]
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        atual = request.form.get("senha_atual", "")
        nova = request.form.get("senha_nova", "")
        usuario = db.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
        if not nome:
            flash("O nome não pode ficar vazio.", "erro")
        elif nova and usuario["senha"] != hash_senha(atual):
            flash("A senha atual está errada.", "erro")
        else:
            db.execute("UPDATE usuarios SET nome = ? WHERE id = ?", (nome, uid))
            if nova:
                db.execute("UPDATE usuarios SET senha = ? WHERE id = ?", (hash_senha(nova), uid))
            db.commit()
            session["nome"] = nome
            flash("Perfil atualizado.", "ok")
            return redirect(url_for("perfil"))
    usuario = db.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
    return render_template("perfil.html", usuario=usuario)


# ---------------------------------------------------------------- usuários (admin)

@app.route("/usuarios")
@login_obrigatorio("admin")
def usuarios():
    db = conectar()
    busca = request.args.get("q", "").strip()
    perfil = request.args.get("perfil", "")
    sql = "SELECT * FROM usuarios WHERE nome LIKE ?"
    params = [f"%{busca}%"]
    if perfil in PERFIS:
        sql += " AND perfil = ?"
        params.append(perfil)
    lista = db.execute(sql + " ORDER BY perfil, nome", params).fetchall()
    return render_template("usuarios.html", usuarios=lista, busca=busca, perfil=perfil)


@app.route("/usuarios/novo", methods=["GET", "POST"])
@app.route("/usuarios/<int:uid>/editar", methods=["GET", "POST"])
@login_obrigatorio("admin")
def usuario_form(uid=None):
    db = conectar()
    usuario = None
    if uid:
        usuario = db.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone() or abort(404)
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        perfil = request.form.get("perfil", "")
        senha = request.form.get("senha", "")
        erro = None
        if not nome or not email or perfil not in PERFIS:
            erro = "Preencha nome, e-mail e perfil."
        elif not uid and not senha:
            erro = "Informe uma senha para o novo usuário."
        else:
            existe = db.execute("SELECT id FROM usuarios WHERE email = ? AND id != ?", (email, uid or 0)).fetchone()
            if existe:
                erro = "Já existe um usuário com esse e-mail."
        if erro:
            flash(erro, "erro")
        else:
            if uid:
                db.execute("UPDATE usuarios SET nome = ?, email = ?, perfil = ? WHERE id = ?",
                           (nome, email, perfil, uid))
                if senha:
                    db.execute("UPDATE usuarios SET senha = ? WHERE id = ?", (hash_senha(senha), uid))
            else:
                db.execute("INSERT INTO usuarios (nome, email, senha, perfil) VALUES (?, ?, ?, ?)",
                           (nome, email, hash_senha(senha), perfil))
            db.commit()
            flash("Usuário salvo com sucesso.", "ok")
            return redirect(url_for("usuarios"))
    return render_template("usuario_form.html", usuario=usuario)


@app.route("/usuarios/<int:uid>/excluir", methods=["POST"])
@login_obrigatorio("admin")
def usuario_excluir(uid):
    if uid == session["usuario_id"]:
        flash("Você não pode excluir a própria conta.", "erro")
    else:
        db = conectar()
        db.execute("DELETE FROM usuarios WHERE id = ?", (uid,))
        db.commit()
        flash("Usuário excluído.", "ok")
    return redirect(url_for("usuarios"))


# ---------------------------------------------------------------- turmas (admin)

@app.route("/turmas")
@login_obrigatorio("admin")
def turmas():
    db = conectar()
    lista = db.execute(
        "SELECT t.*, (SELECT COUNT(*) FROM matriculas m WHERE m.turma_id = t.id) AS total_alunos "
        "FROM turmas t ORDER BY t.ano DESC, t.nome").fetchall()
    return render_template("turmas.html", turmas=lista)


@app.route("/turmas/nova", methods=["GET", "POST"])
@app.route("/turmas/<int:tid>/editar", methods=["GET", "POST"])
@login_obrigatorio("admin")
def turma_form(tid=None):
    db = conectar()
    turma = None
    if tid:
        turma = db.execute("SELECT * FROM turmas WHERE id = ?", (tid,)).fetchone() or abort(404)
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        ano = request.form.get("ano", "")
        turno = request.form.get("turno", "")
        if not nome or not ano.isdigit() or turno not in TURNOS:
            flash("Preencha nome, ano e turno corretamente.", "erro")
        else:
            if tid:
                db.execute("UPDATE turmas SET nome = ?, ano = ?, turno = ? WHERE id = ?", (nome, int(ano), turno, tid))
            else:
                db.execute("INSERT INTO turmas (nome, ano, turno) VALUES (?, ?, ?)", (nome, int(ano), turno))
            db.commit()
            flash("Turma salva com sucesso.", "ok")
            return redirect(url_for("turmas"))
    return render_template("turma_form.html", turma=turma, turnos=TURNOS)


@app.route("/turmas/<int:tid>/excluir", methods=["POST"])
@login_obrigatorio("admin")
def turma_excluir(tid):
    db = conectar()
    db.execute("DELETE FROM turmas WHERE id = ?", (tid,))
    db.commit()
    flash("Turma excluída.", "ok")
    return redirect(url_for("turmas"))


@app.route("/turmas/<int:tid>/alunos", methods=["GET", "POST"])
@login_obrigatorio("admin")
def turma_alunos(tid):
    db = conectar()
    turma = db.execute("SELECT * FROM turmas WHERE id = ?", (tid,)).fetchone() or abort(404)
    if request.method == "POST":
        aluno_id = request.form.get("aluno_id", type=int)
        aluno = db.execute("SELECT id FROM usuarios WHERE id = ? AND perfil = 'aluno'", (aluno_id,)).fetchone()
        if aluno:
            db.execute("INSERT OR IGNORE INTO matriculas (aluno_id, turma_id) VALUES (?, ?)", (aluno_id, tid))
            db.commit()
            flash("Aluno matriculado.", "ok")
        return redirect(url_for("turma_alunos", tid=tid))
    matriculados = db.execute(
        "SELECT m.id AS matricula_id, m.data_matricula, u.* FROM matriculas m "
        "JOIN usuarios u ON u.id = m.aluno_id WHERE m.turma_id = ? ORDER BY u.nome", (tid,)).fetchall()
    disponiveis = db.execute(
        "SELECT * FROM usuarios WHERE perfil = 'aluno' AND id NOT IN "
        "(SELECT aluno_id FROM matriculas WHERE turma_id = ?) ORDER BY nome", (tid,)).fetchall()
    return render_template("turma_alunos.html", turma=turma, matriculados=matriculados, disponiveis=disponiveis)


@app.route("/matriculas/<int:mid>/excluir", methods=["POST"])
@login_obrigatorio("admin")
def matricula_excluir(mid):
    db = conectar()
    matricula = db.execute("SELECT * FROM matriculas WHERE id = ?", (mid,)).fetchone() or abort(404)
    db.execute("DELETE FROM matriculas WHERE id = ?", (mid,))
    db.commit()
    flash("Matrícula removida.", "ok")
    return redirect(url_for("turma_alunos", tid=matricula["turma_id"]))


# ---------------------------------------------------------------- disciplinas (admin)

@app.route("/disciplinas")
@login_obrigatorio("admin")
def disciplinas():
    db = conectar()
    lista = db.execute(
        "SELECT d.*, t.nome AS turma, u.nome AS professor FROM disciplinas d "
        "JOIN turmas t ON t.id = d.turma_id LEFT JOIN usuarios u ON u.id = d.professor_id "
        "ORDER BY t.nome, d.nome").fetchall()
    return render_template("disciplinas.html", disciplinas=lista)


@app.route("/disciplinas/nova", methods=["GET", "POST"])
@app.route("/disciplinas/<int:did>/editar", methods=["GET", "POST"])
@login_obrigatorio("admin")
def disciplina_form(did=None):
    db = conectar()
    disciplina = None
    if did:
        disciplina = db.execute("SELECT * FROM disciplinas WHERE id = ?", (did,)).fetchone() or abort(404)
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        carga = request.form.get("carga_horaria", "")
        turma_id = request.form.get("turma_id", type=int)
        professor_id = request.form.get("professor_id", type=int)
        if not nome or not carga.isdigit() or not turma_id:
            flash("Preencha nome, carga horária e turma.", "erro")
        else:
            valores = (nome, int(carga), turma_id, professor_id)
            if did:
                db.execute("UPDATE disciplinas SET nome = ?, carga_horaria = ?, turma_id = ?, professor_id = ? "
                           "WHERE id = ?", valores + (did,))
            else:
                db.execute("INSERT INTO disciplinas (nome, carga_horaria, turma_id, professor_id) "
                           "VALUES (?, ?, ?, ?)", valores)
            db.commit()
            flash("Disciplina salva com sucesso.", "ok")
            return redirect(url_for("disciplinas"))
    turmas_ = db.execute("SELECT * FROM turmas ORDER BY nome").fetchall()
    professores = db.execute("SELECT * FROM usuarios WHERE perfil = 'professor' ORDER BY nome").fetchall()
    return render_template("disciplina_form.html", disciplina=disciplina, turmas=turmas_, professores=professores)


@app.route("/disciplinas/<int:did>/excluir", methods=["POST"])
@login_obrigatorio("admin")
def disciplina_excluir(did):
    db = conectar()
    db.execute("DELETE FROM disciplinas WHERE id = ?", (did,))
    db.commit()
    flash("Disciplina excluída.", "ok")
    return redirect(url_for("disciplinas"))


# ---------------------------------------------------------------- notas (professor)

@app.route("/notas")
@login_obrigatorio("professor", "admin")
def notas():
    db = conectar()
    sql = ("SELECT d.*, t.nome AS turma, u.nome AS professor FROM disciplinas d "
           "JOIN turmas t ON t.id = d.turma_id LEFT JOIN usuarios u ON u.id = d.professor_id")
    if session["perfil"] == "professor":
        lista = db.execute(sql + " WHERE d.professor_id = ? ORDER BY d.nome", (session["usuario_id"],)).fetchall()
    else:
        lista = db.execute(sql + " ORDER BY t.nome, d.nome").fetchall()
    return render_template("notas.html", disciplinas=lista)


@app.route("/notas/<int:did>", methods=["GET", "POST"])
@login_obrigatorio("professor", "admin")
def notas_disciplina(did):
    db = conectar()
    disciplina = db.execute(
        "SELECT d.*, t.nome AS turma FROM disciplinas d JOIN turmas t ON t.id = d.turma_id WHERE d.id = ?",
        (did,)).fetchone() or abort(404)
    if session["perfil"] == "professor" and disciplina["professor_id"] != session["usuario_id"]:
        abort(403)
    alunos = db.execute(
        "SELECT u.* FROM usuarios u JOIN matriculas m ON m.aluno_id = u.id "
        "WHERE m.turma_id = ? ORDER BY u.nome", (disciplina["turma_id"],)).fetchall()
    if request.method == "POST":
        erros = 0
        for aluno in alunos:
            for bim in range(1, 5):
                campo = request.form.get(f"nota_{aluno['id']}_{bim}", "").replace(",", ".").strip()
                if campo == "":
                    db.execute("DELETE FROM notas WHERE aluno_id = ? AND disciplina_id = ? AND bimestre = ?",
                               (aluno["id"], did, bim))
                    continue
                try:
                    valor = float(campo)
                    if not 0 <= valor <= 10:
                        raise ValueError
                except ValueError:
                    erros += 1
                    continue
                db.execute(
                    "INSERT INTO notas (aluno_id, disciplina_id, bimestre, valor) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT (aluno_id, disciplina_id, bimestre) DO UPDATE SET valor = excluded.valor",
                    (aluno["id"], did, bim, valor))
        db.commit()
        if erros:
            flash(f"Notas salvas, mas {erros} valor(es) inválido(s) foram ignorados (use 0 a 10).", "erro")
        else:
            flash("Notas salvas com sucesso.", "ok")
        return redirect(url_for("notas_disciplina", did=did))
    lancadas = {}
    for n in db.execute("SELECT * FROM notas WHERE disciplina_id = ?", (did,)):
        lancadas[(n["aluno_id"], n["bimestre"])] = n["valor"]
    return render_template("notas_disciplina.html", disciplina=disciplina, alunos=alunos, lancadas=lancadas)


# ---------------------------------------------------------------- boletim

@app.route("/boletim/<int:aluno_id>")
@login_obrigatorio()
def boletim(aluno_id):
    db = conectar()
    aluno = db.execute("SELECT * FROM usuarios WHERE id = ? AND perfil = 'aluno'", (aluno_id,)).fetchone()
    if not aluno:
        abort(404)
    disciplinas_ = db.execute(
        "SELECT d.id, d.nome, t.nome AS turma, u.nome AS professor FROM disciplinas d "
        "JOIN matriculas m ON m.turma_id = d.turma_id JOIN turmas t ON t.id = d.turma_id "
        "LEFT JOIN usuarios u ON u.id = d.professor_id WHERE m.aluno_id = ? ORDER BY d.nome",
        (aluno_id,)).fetchall()
    linhas = []
    for d in disciplinas_:
        notas_ = {n["bimestre"]: n["valor"] for n in db.execute(
            "SELECT bimestre, valor FROM notas WHERE aluno_id = ? AND disciplina_id = ?", (aluno_id, d["id"]))}
        media = round(sum(notas_.values()) / len(notas_), 1) if notas_ else None
        linhas.append({"disciplina": d, "notas": notas_, "media": media})
    return render_template("boletim.html", aluno=aluno, linhas=linhas)


@app.route("/boletins")
@login_obrigatorio("professor", "admin")
def boletins():
    db = conectar()
    alunos = db.execute(
        "SELECT u.*, GROUP_CONCAT(t.nome, ', ') AS turmas FROM usuarios u "
        "LEFT JOIN matriculas m ON m.aluno_id = u.id LEFT JOIN turmas t ON t.id = m.turma_id "
        "WHERE u.perfil = 'aluno' GROUP BY u.id ORDER BY u.nome").fetchall()
    return render_template("boletins.html", alunos=alunos)


# ---------------------------------------------------------------- mural de avisos

@app.route("/mural")
@login_obrigatorio()
def mural():
    db = conectar()
    avisos = db.execute(
        "SELECT a.*, u.nome AS autor, (SELECT COUNT(*) FROM comentarios c WHERE c.aviso_id = a.id) AS total "
        "FROM avisos a JOIN usuarios u ON u.id = a.autor_id ORDER BY a.criado_em DESC, a.id DESC").fetchall()
    return render_template("mural.html", avisos=avisos)


@app.route("/mural/novo", methods=["GET", "POST"])
@login_obrigatorio("professor", "admin")
def aviso_novo():
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        conteudo = request.form.get("conteudo", "").strip()
        if not titulo or not conteudo:
            flash("Preencha título e conteúdo.", "erro")
        else:
            db = conectar()
            db.execute("INSERT INTO avisos (autor_id, titulo, conteudo) VALUES (?, ?, ?)",
                       (session["usuario_id"], titulo, str(escape(conteudo))))
            db.commit()
            flash("Aviso publicado.", "ok")
            return redirect(url_for("mural"))
    return render_template("aviso_form.html")


@app.route("/mural/<int:aid>", methods=["GET", "POST"])
@login_obrigatorio()
def aviso(aid):
    db = conectar()
    aviso_ = db.execute(
        "SELECT a.*, u.nome AS autor FROM avisos a JOIN usuarios u ON u.id = a.autor_id WHERE a.id = ?",
        (aid,)).fetchone() or abort(404)
    if request.method == "POST":
        texto = request.form.get("texto", "").strip()
        if texto:
            db.execute("INSERT INTO comentarios (aviso_id, autor_id, texto) VALUES (?, ?, ?)",
                       (aid, session["usuario_id"], texto))
            db.commit()
            flash("Comentário enviado.", "ok")
        return redirect(url_for("aviso", aid=aid))
    comentarios = db.execute(
        "SELECT c.*, u.nome AS autor, u.perfil FROM comentarios c JOIN usuarios u ON u.id = c.autor_id "
        "WHERE c.aviso_id = ? ORDER BY c.criado_em, c.id", (aid,)).fetchall()
    return render_template("aviso.html", aviso=aviso_, comentarios=comentarios)


@app.route("/mural/<int:aid>/excluir", methods=["POST"])
@login_obrigatorio("professor", "admin")
def aviso_excluir(aid):
    db = conectar()
    aviso_ = db.execute("SELECT * FROM avisos WHERE id = ?", (aid,)).fetchone() or abort(404)
    if session["perfil"] != "admin" and aviso_["autor_id"] != session["usuario_id"]:
        abort(403)
    db.execute("DELETE FROM avisos WHERE id = ?", (aid,))
    db.commit()
    flash("Aviso excluído.", "ok")
    return redirect(url_for("mural"))


criar_banco()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
