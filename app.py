import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import hashlib
import io
import re
import shutil
import zipfile
from datetime import datetime
import fitz  # PyMuPDF
from PIL import Image

# NOVAS IMPORTAÇÕES PARA PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

# --- Inicializar estados globais ---
if 'jump_to_mes' not in st.session_state:
    st.session_state['jump_to_mes'] = None

if 'morador_menu_option' not in st.session_state:
    st.session_state['morador_menu_option'] = "📊 O Meu Plano"

# Configuração da página Streamlit
st.set_page_config(
    page_title="Gestão Condomínio José Fontana N.º 2",
    page_icon="🏢",
    layout="wide"
)

# Caminhos dos Ficheiros Locais de Persistência
FILE_MOVIMENTOS = "movimentos_banco.csv"
FILE_GASTOS = "gastos_faturas.csv"
FILE_ACTAS = "actas.json"
FILE_CONTACTOS = "contactos.json"
FILE_AUDIT = "auditoria.json"
DIR_ANEXOS = "faturas_anexas"
DIR_ACTAS = "actas_anexas"
DIR_BACKUPS = "backups"

# Contactos predefinidos de fábrica
CONTACTOS_INICIAIS = {
    "RC Esq": {"nome": "Moisés Alejandro da Silva", "email": "a.m.s.alves@sapo.pt", "telemovel": "910000001", "nif": "276868340", "quota": 15.0, "perfil": "Ambos", "password": "fontana2", "must_change": False},
    "RC Dir": {"nome": "Pedro Daniel Lopes Veríssimo", "email": "pedro.verissimo@gmail.com", "telemovel": "910000002", "nif": "218477910", "quota": 15.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "1º Esq": {"nome": "António Santos Alves", "email": "antonio.santosalves@gmail.com", "telemovel": "910000003", "nif": "189728868", "quota": 15.0, "perfil": "Ambos", "password": "fontana2", "must_change": False},
    "1º Dir": {"nome": "Rosário Ganhão", "email": "zaritaganhao@gmail.com", "telemovel": "910000004", "nif": "123456789", "quota": 15.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "2º Esq": {"nome": "Inês Ferreira / Regina Alves", "email": "irjoferreira@gmail.com", "telemovel": "910000005", "nif": "214183408", "quota": 15.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "2º Dir": {"nome": "António Alves", "email": "toalves78@googlemail.com", "telemovel": "910000006", "nif": "182876110", "quota": 15.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "3º Esq": {"nome": "Lúcia de Jesus", "email": "lucia.catarina.jesus@gmail.com", "telemovel": "910000007", "nif": "147306205", "quota": 15.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "3º Dir": {"nome": "Por Atribuir", "email": "morador3d@fontana2.com", "telemovel": "910000008", "nif": "123456782", "quota": 15.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "Garagem A": {"nome": "Tomás Luís Santos Pinheiro", "email": "samotpinheiro@gmail.com", "telemovel": "910000009", "nif": "115586911", "quota": 5.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "Garagem B": {"nome": "Cristina Marques", "email": "carreiramarques38@gmail.com", "telemovel": "910000010", "nif": "123456780", "quota": 5.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "Garagem C": {"nome": "Tiago Faria", "email": "tiago.faria@gmail.com", "telemovel": "910000011", "nif": "123456779", "quota": 5.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "Garagem D": {"nome": "Albertina Rei / Carlos Rei", "email": "carlos.rei@gmail.com", "telemovel": "910000012", "nif": "123456778", "quota": 5.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "Garagem E": {"nome": "José Correia", "email": "jose.d.correia@gmail.com", "telemovel": "910000013", "nif": "123456777", "quota": 5.0, "perfil": "Morador", "password": "fontana2", "must_change": False},
    "Administração do Condomínio": {"nome": "Despesas Comunes / Bancarias", "email": "admin@fontana2.com", "telemovel": "910000000", "nif": "500000000", "quota": 0.0, "perfil": "Administrador", "password": "admin", "must_change": False}
}

# --- SISTEMA DE AUDITORIA E LOGS ---
def carregar_logs():
    if os.path.exists(FILE_AUDIT):
        with open(FILE_AUDIT, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def registrar_acao(acao, detalhes):
    logs = carregar_logs()
    novo_log = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "utilizador": st.session_state.get('user_email', 'Sistema'),
        "acao": acao,
        "detalhes": detalhes
    }
    logs.append(novo_log)
    if len(logs) > 1000:
        logs = logs[-1000:]
    with open(FILE_AUDIT, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=4)

# --- SISTEMA DE BACKUP, RETENÇÃO E RESTAURO INTELIGENTE ---
def gerar_backup_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for f in [FILE_MOVIMENTOS, FILE_GASTOS, FILE_ACTAS, FILE_CONTACTOS, FILE_AUDIT]:
            if os.path.exists(f):
                zipf.write(f, arcname=f)
        for pasta in [DIR_ANEXOS, DIR_ACTAS]:
            if os.path.exists(pasta):
                for root, dirs, files in os.walk(pasta):
                    for file in files:
                        caminho_completo = os.path.join(root, file)
                        caminho_relativo = os.path.relpath(caminho_completo, ".")
                        zipf.write(caminho_completo, arcname=caminho_relativo)
    buffer.seek(0)
    return buffer

def backup_automatico():
    os.makedirs(DIR_BACKUPS, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_ficheiro = os.path.join(DIR_BACKUPS, f"backup_automatico_{timestamp}.zip")
    try:
        with zipfile.ZipFile(nome_ficheiro, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f in [FILE_MOVIMENTOS, FILE_GASTOS, FILE_ACTAS, FILE_CONTACTOS, FILE_AUDIT]:
                if os.path.exists(f):
                    zipf.write(f, arcname=f)
            for pasta in [DIR_ANEXOS, DIR_ACTAS]:
                if os.path.exists(pasta):
                    for root, dirs, files in os.walk(pasta):
                        for file in files:
                            caminho_completo = os.path.join(root, file)
                            caminho_relativo = os.path.relpath(caminho_completo, ".")
                            zipf.write(caminho_completo, arcname=caminho_relativo)

        backups_existentes = sorted(
            [os.path.join(DIR_BACKUPS, f) for f in os.listdir(DIR_BACKUPS) if f.startswith("backup_automatico_") and f.endswith('.zip')],
            key=os.path.getmtime,
            reverse=True
        )

        if len(backups_existentes) > 5:
            for velho_backup in backups_existentes[5:]:
                try:
                    os.remove(velho_backup)
                except Exception as e:
                    print(f"Erro ao remover backup antigo {velho_backup}: {e}")

    except Exception as e:
        print(f"Erro no backup automático: {e}")

def verificar_backup_diario():
    os.makedirs(DIR_BACKUPS, exist_ok=True)
    hoje = datetime.now().strftime("%Y%m%d")
    backups = [f for f in os.listdir(DIR_BACKUPS) if f.startswith(f"backup_automatico_{hoje}")]
    if not backups:
        backup_automatico()

verificar_backup_diario()

def restaurar_backup_zip(uploaded_file):
    try:
        with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
            extract_dir = "temp_restore"
            os.makedirs(extract_dir, exist_ok=True)
            zip_ref.extractall(extract_dir)

            relatorio = []

            path_backup_contactos = os.path.join(extract_dir, FILE_CONTACTOS)
            if os.path.exists(path_backup_contactos):
                with open(path_backup_contactos, "r", encoding="utf-8") as f:
                    backup_contactos = json.load(f)

                if os.path.exists(FILE_CONTACTOS):
                    with open(FILE_CONTACTOS, "r", encoding="utf-8") as f:
                        atual_contactos = json.load(f)
                else:
                    atual_contactos = {}

                adicionados_cont = 0
                for fracao, info in backup_contactos.items():
                    if fracao not in atual_contactos:
                        atual_contactos[fracao] = info
                        adicionados_cont += 1

                with open(FILE_CONTACTOS, "w", encoding="utf-8") as f:
                    json.dump(atual_contactos, f, ensure_ascii=False, indent=4)
                relatorio.append(f"👥 Contactos: {adicionados_cont} fracções novas integradas.")

            path_backup_mov = os.path.join(extract_dir, FILE_MOVIMENTOS)
            if os.path.exists(path_backup_mov):
                df_backup_mov = pd.read_csv(path_backup_mov, dtype={'Hash_Movimento': str, 'Mes_Ano_Quota': str, 'Fatura_Despesa_ID': str})
                if os.path.exists(FILE_MOVIMENTOS):
                    dfAtual_mov = pd.read_csv(FILE_MOVIMENTOS, dtype={'Hash_Movimento': str, 'Mes_Ano_Quota': str, 'Fatura_Despesa_ID': str})
                    if "Hash_Movimento" in df_backup_mov.columns and "Hash_Movimento" in dfAtual_mov.columns:
                        hashes_atuais = set(dfAtual_mov["Hash_Movimento"].dropna())
                        novos_movs = df_backup_mov[~df_backup_mov["Hash_Movimento"].isin(hashes_atuais)]
                        df_final_mov = pd.concat([dfAtual_mov, novos_movs], ignore_index=True)
                        adicionados_mov = len(novos_movs)
                    else:
                        df_final_mov = pd.concat([dfAtual_mov, df_backup_mov]).drop_duplicates()
                        adicionados_mov = len(df_final_mov) - len(dfAtual_mov)
                else:
                    df_final_mov = df_backup_mov
                    adicionados_mov = len(df_backup_mov)

                df_final_mov.to_csv(FILE_MOVIMENTOS, index=False)
                relatorio.append(f"🏦 Movimentos Bancários: {adicionados_mov} novos movimentos adicionados.")

            path_backup_gastos = os.path.join(extract_dir, FILE_GASTOS)
            if os.path.exists(path_backup_gastos):
                df_backup_gastos = pd.read_csv(path_backup_gastos, dtype={'Hash_Movimento': str, 'ID': str})
                if os.path.exists(FILE_GASTOS):
                    dfAtual_gastos = pd.read_csv(FILE_GASTOS, dtype={'Hash_Movimento': str, 'ID': str})
                    if "ID" in df_backup_gastos.columns and "ID" in dfAtual_gastos.columns:
                        ids_atuais = set(dfAtual_gastos["ID"].dropna())
                        novos_gastos = df_backup_gastos[~df_backup_gastos["ID"].isin(ids_atuais)]
                        df_final_gastos = pd.concat([dfAtual_gastos, novos_gastos], ignore_index=True)
                        adicionados_gastos = len(novos_gastos)
                    else:
                        df_final_gastos = pd.concat([dfAtual_gastos, df_backup_gastos]).drop_duplicates()
                        adicionados_gastos = len(df_final_gastos) - len(dfAtual_gastos)
                else:
                    df_final_gastos = df_backup_gastos
                    adicionados_gastos = len(df_backup_gastos)

                df_final_gastos.to_csv(FILE_GASTOS, index=False)
                relatorio.append(f"🧾 Gastos/Faturas: {adicionados_gastos} faturas integradas.")

            path_backup_actas = os.path.join(extract_dir, FILE_ACTAS)
            if os.path.exists(path_backup_actas):
                with open(path_backup_actas, "r", encoding="utf-8") as f:
                    backup_actas = json.load(f)
                if os.path.exists(FILE_ACTAS):
                    with open(FILE_ACTAS, "r", encoding="utf-8") as f:
                        atual_actas = json.load(f)
                else:
                    atual_actas = []

                ids_actas = {a.get("id") for a in atual_actas}
                adicionadas_actas = 0
                for acta in backup_actas:
                    if acta.get("id") not in ids_actas:
                        atual_actas.append(acta)
                        adicionadas_actas += 1

                with open(FILE_ACTAS, "w", encoding="utf-8") as f:
                    json.dump(atual_actas, f, ensure_ascii=False, indent=4)
                relatorio.append(f"📝 Actas: {adicionadas_actas} novas actas adicionadas.")

            for folder in [DIR_ANEXOS, DIR_ACTAS]:
                src_folder = os.path.join(extract_dir, folder)
                if os.path.exists(src_folder):
                    os.makedirs(folder, exist_ok=True)
                    for root, dirs, files in os.walk(src_folder):
                        for file in files:
                            src_file = os.path.join(root, file)
                            dest_file = os.path.join(folder, file)
                            if not os.path.exists(dest_file):
                                with open(src_file, "rb") as sf, open(dest_file, "wb") as df:
                                    df.write(sf.read())
                    relatorio.append(f"📁 Pasta '{folder}': Ficheiros em falta repostos com sucesso.")

            shutil.rmtree(extract_dir, ignore_index=True)
            return True, relatorio
    except Exception as e:
        return False, [f"Erro ao processar o backup: {str(e)}"]

# --- FUNÇÕES DE PERSISTÊNCIA E DADOS ---
def salvar_contactos(contactos):
    with open(FILE_CONTACTOS, "w", encoding="utf-8") as f:
        json.dump(contactos, f, ensure_ascii=False, indent=4)

def carregar_contactos():
    if os.path.exists(FILE_CONTACTOS):
        with open(FILE_CONTACTOS, "r", encoding="utf-8") as f:
            dados = json.load(f)
        alterado = False
        for fracao, default_info in CONTACTOS_INICIAIS.items():
            if fracao not in dados:
                dados[fracao] = default_info
                alterado = True
            else:
                for k, v in default_info.items():
                    if k not in dados[fracao]:
                        dados[fracao][k] = v
                        alterado = True
        if alterado:
            salvar_contactos(dados)
        return dados
    else:
        salvar_contactos(CONTACTOS_INICIAIS)
        return CONTACTOS_INICIAIS

def carregar_movimentos():
    expected_cols = [
        "Data Mov", "Data Val", "Descrição", "Valor (€)", "Saldo (€)",
        "Reconciliado", "Fracção Associada", "Mes_Ano_Quota", "Fatura_Despesa_ID", "Hash_Movimento",
        "Administrador Validador"
    ]
    if os.path.exists(FILE_MOVIMENTOS):
        try:
            df = pd.read_csv(FILE_MOVIMENTOS, dtype={'Hash_Movimento': str, 'Mes_Ano_Quota': str, 'Fatura_Despesa_ID': str})
        except Exception:
            df = pd.DataFrame()

        df = df.loc[:, ~df.columns.duplicated()]

        for col in expected_cols:
            if col not in df.columns:
                df[col] = None

        df = df[expected_cols]
        if 'Data Mov' in df.columns:
            df['Data Mov'] = pd.to_datetime(df['Data Mov'], format='%d/%m/%Y', errors='coerce')
        if 'Data Val' in df.columns:
            df['Data Val'] = pd.to_datetime(df['Data Val'], format='%d/%m/%Y', errors='coerce')
        return df
    else:
        return pd.DataFrame(columns=expected_cols)

def salvar_movimentos(df):
    df_copy = df.copy()
    df_copy = df_copy.loc[:, ~df_copy.columns.duplicated()]
    if 'Data Mov' in df_copy.columns and pd.api.types.is_datetime64_any_dtype(df_copy['Data Mov']):
        df_copy['Data Mov'] = df_copy['Data Mov'].dt.strftime('%d/%m/%Y')
    if 'Data Val' in df_copy.columns and pd.api.types.is_datetime64_any_dtype(df_copy['Data Val']):
        df_copy['Data Val'] = df_copy['Data Val'].dt.strftime('%d/%m/%Y')
    df_copy.to_csv(FILE_MOVIMENTOS, index=False)

def carregar_gastos():
    if os.path.exists(FILE_GASTOS):
        df = pd.read_csv(FILE_GASTOS, dtype={'Hash_Movimento': str, 'ID': str})
        if 'ID' not in df.columns and 'Fatura/Recibo' in df.columns:
            df['ID'] = df['Fatura/Recibo']
        return df
    return pd.DataFrame(columns=["ID", "Data", "Fornecedor", "Descrição", "Valor (€)", "Categoria", "Nome_Ficheiro", "Hash_Movimento"])

def salvar_gastos(df):
    df.to_csv(FILE_GASTOS, index=False)

def carregar_actas():
    if os.path.exists(FILE_ACTAS):
        with open(FILE_ACTAS, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_actas(actas):
    with open(FILE_ACTAS, "w", encoding="utf-8") as f:
        json.dump(actas, f, ensure_ascii=False, indent=4)

def gerar_hash_movimento(data, descr, valor):
    string_unica = f"{data}_{descr}_{valor}"
    return hashlib.md5(string_unica.encode('utf-8')).hexdigest()

def extrair_texto_pdf(ficheiro_bytes):
    doc = fitz.open(stream=ficheiro_bytes, filetype="pdf")
    texto = ""
    for pagina in doc:
        texto += pagina.get_text("text")
    if len(texto.strip()) < 50:
        try:
            import pytesseract
            texto = ""
            for pagina in doc:
                pix = pagina.get_pixmap()
                img = Image.open(io.BytesIO(pix.tobytes()))
                texto += pytesseract.image_to_string(img, lang='por')
        except Exception:
            pass
    return texto

def processar_extrato_bpi(texto):
    linhas = texto.split('\n')
    movimentos = []
    padrao_data = re.compile(r'^\d{2}/\d{2}/\d{4}$')
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if padrao_data.match(linha):
            try:
                data_mov = linha
                data_val = linhas[i+1].strip() if i+1 < len(linhas) and padrao_data.match(linhas[i+1].strip()) else data_mov
                idx_val = i+1 if padrao_data.match(linhas[i+1].strip()) else i
                descr_linhas = []
                j = idx_val + 1
                while j < len(linhas):
                    l_test = linhas[j].strip()
                    if padrao_data.match(l_test):
                        break
                    val_clean = l_test.replace('.', '').replace(',', '.')
                    try:
                        valor_num = float(val_clean)
                        if len(descr_linhas) > 0:
                            j += 1
                            if j < len(linhas):
                                saldo_clean = linhas[j].strip().replace('.', '').replace(',', '.')
                                try:
                                    saldo_num = float(saldo_clean)
                                    descr_completa = " ".join(descr_linhas)
                                    hash_mov = gerar_hash_movimento(data_mov, descr_completa, valor_num)
                                    movimentos.append({
                                        "Data Mov": data_mov,
                                        "Data Val": data_val,
                                        "Descrição": descr_completa,
                                        "Valor (€)": valor_num,
                                        "Saldo (€)": saldo_num,
                                        "Reconciliado": "Não",
                                        "Fracção Associada": "Não Identificada",
                                        "Mes_Ano_Quota": None,
                                        "Fatura_Despesa_ID": None,
                                        "Hash_Movimento": hash_mov,
                                        "Administrador Validador": None
                                    })
                                    i = j
                                    break
                                except ValueError:
                                    pass
                    except ValueError:
                        descr_linhas.append(l_test)
                    j += 1
            except Exception:
                pass
        i += 1
    return movimentos

# --- FUNÇÃO PARA GERAR RECIBO EM PDF ---
def gerar_recibo_pdf(dados_recibo, info_admin):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=18,
        leading=24,
        alignment=1,
        spaceAfter=10,
        textColor=colors.HexColor('#2c3e50')
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=1,
        spaceAfter=25,
        textColor=colors.HexColor('#7f8c8d')
    )

    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#2c3e50')
    )

    cell_bold_style = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#2c3e50')
    )

    cell_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=11,
        leading=13,
        fontName='Helvetica-Bold',
        textColor=colors.whitesmoke
    )

    story.append(Paragraph("CONDOMÍNIO PRACETA JOSÉ FONTANA N.º 2", title_style))
    story.append(Paragraph("PÓVOA DE SANTA IRIA", subtitle_style))
    story.append(Spacer(1, 15))

    dados_table = [
        [Paragraph('CONCEITO', cell_header_style), Paragraph('DETALHE', cell_header_style)],
        [Paragraph('N.º Recibo / Ref:', cell_bold_style), Paragraph(str(dados_recibo['ref_id']), cell_style)],
        [Paragraph('Data de Emissão:', cell_bold_style), Paragraph(str(dados_recibo['data_emissao']), cell_style)],
        [Paragraph('Fracção:', cell_bold_style), Paragraph(str(dados_recibo['fracao']), cell_style)],
        [Paragraph('Titular:', cell_bold_style), Paragraph(str(dados_recibo['titular']), cell_style)],
        [Paragraph('NIF:', cell_bold_style), Paragraph(str(dados_recibo['nif']), cell_style)],
    ]

    table = Table(dados_table, colWidths=[4.8*cm, 10.2*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(table)
    story.append(Spacer(1, 25))

    story.append(Paragraph("<b>DETALHES DO PAGAMENTO</b>", ParagraphStyle('Section', fontSize=12, leading=16, textColor=colors.HexColor('#2c3e50'), alignment=1)))
    story.append(Spacer(1, 10))

    pagto_data = [
        [Paragraph('CONCEITO', cell_header_style), Paragraph('DETALHE', cell_header_style)],
        [Paragraph('Valor Recebido:', cell_bold_style), Paragraph(f"<b>{dados_recibo['valor']:.2f} €</b>", cell_style)],
        [Paragraph('Referente a:', cell_bold_style), Paragraph(str(dados_recibo['meses_pagos']), cell_style)],
        [Paragraph('Data da Transferência:', cell_bold_style), Paragraph(str(dados_recibo['data_processamento']), cell_style)],
        [Paragraph('Conta Bancária:', cell_bold_style), Paragraph(str(dados_recibo['conta_bancaria']), cell_style)],
    ]

    table2 = Table(pagto_data, colWidths=[4.8*cm, 10.2*cm])
    table2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(table2)
    story.append(Spacer(1, 35))

    story.append(Paragraph("<b>VALIDADO POR</b>", ParagraphStyle('Section', fontSize=12, leading=16, textColor=colors.HexColor('#2c3e50'), alignment=1)))
    story.append(Spacer(1, 10))

    firma_style = ParagraphStyle('Firma', alignment=1, fontSize=10, textColor=colors.HexColor('#7f8c8d'))
    story.append(Paragraph("____________________________________________", firma_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph(f"<b>{info_admin['nome']}</b>", ParagraphStyle('AdminName', alignment=1, fontSize=11, textColor=colors.HexColor('#2c3e50'))))
    story.append(Paragraph(f"Cargo: {info_admin['cargo']}", ParagraphStyle('AdminCargo', alignment=1, fontSize=9, textColor=colors.HexColor('#7f8c8d'))))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Depósito/Transferência Bancária Confirmada", ParagraphStyle('Validation', alignment=1, fontSize=9, textColor=colors.HexColor('#27ae60'), fontName='Helvetica-Bold')))

    story.append(Spacer(1, 40))
    story.append(Paragraph("Obrigado pelo pagamento das quotas.", ParagraphStyle('Footer', alignment=1, fontSize=9, textColor=colors.HexColor('#95a5a6'))))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- FUNÇÃO PARA OBTER O ADMINISTRADOR DINÂMICO ---
def obter_info_admin():
    user_email = st.session_state.get('user_email', '').lower()

    # 1. Procurar o utilizador atual nos contactos (excluindo a conta genérica se houver outra fração associada ao e-mail)
    for fracao, info in contactos_db.items():
        if info.get('email', '').lower() == user_email and fracao != "Administração do Condomínio":
            return {
                'nome': info.get('nome', 'Administrador do Condomínio'),
                'cargo': 'Administrador do Condomínio'
            }

    # 2. Se for a conta admin genérica (admin@fontana2.com), procurar condómino com perfil "Ambos" ou "Administrador"
    for fracao, info in contactos_db.items():
        if info.get('perfil') in ['Administrador', 'Ambos'] and fracao != "Administração do Condomínio":
            return {
                'nome': info.get('nome', 'Administrador do Condomínio'),
                'cargo': 'Administrador do Condomínio'
            }

    return {
        'nome': 'Administrador do Condomínio',
        'cargo': 'Administrador do Condomínio'
    }

# --- SESSÃO & AUTENTICAÇÃO ---
contactos_db = carregar_contactos()
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
    st.session_state['user_email'] = None
    st.session_state['user_role'] = None
    st.session_state['user_fracao'] = None
    st.session_state['must_change'] = False

if not st.session_state['authenticated']:
    st.title("🏢 Gestão Condomínio José Fontana N.º 2")
    st.subheader("Portal de Acesso Autenticado")

    with st.form("login_form"):
        email_input = st.text_input("E-mail de Acesso")
        password_input = st.text_input("Palavra-passe", type="password")
        submit_button = st.form_submit_button("Iniciar Sessão", use_container_width=True)

        if submit_button:
            if email_input == "admin@fontana2.com" and password_input == "admin":
                st.session_state['authenticated'] = True
                st.session_state['user_email'] = email_input
                st.session_state['user_role'] = "Administrador"
                st.session_state['user_fracao'] = "Admin"
                registrar_acao("Login Administrador", "Acesso ao painel de administração.")
                st.rerun()
            else:
                user_found = False
                for fracao, info in contactos_db.items():
                    if info.get('email', '').lower() == email_input.lower():
                        user_found = True
                        pwd_cadastrada = info.get('password', 'fontana2')
                        if pwd_cadastrada == password_input:
                            st.session_state['authenticated'] = True
                            st.session_state['user_email'] = email_input
                            st.session_state['user_role'] = info.get('perfil', 'Morador')
                            st.session_state['user_fracao'] = fracao
                            st.session_state['must_change'] = info.get('must_change', False)
                            registrar_acao("Login Condómino", f"Acesso de {fracao} ({email_input}).")
                            st.rerun()
                        else:
                            st.error("Palavra-passe incorreta.")
                        break
                if not user_found:
                    st.error("Utilizador não encontrado no sistema.")
    st.stop()

# --- FORÇAR ALTERAÇÃO DE PASSWORD ---
if st.session_state.get('must_change', False):
    st.warning("⚠️ O Administrador solicitou a alteração da sua palavra-passe de acesso.")
    with st.form("form_alterar_pwd_obrigatorio"):
        nova_pwd = st.text_input("Nova Palavra-passe", type="password")
        confirma_pwd = st.text_input("Confirmar Nova Palavra-passe", type="password")
        btn_salvar_pwd = st.form_submit_button("Atualizar Palavra-passe")

        if btn_salvar_pwd:
            if nova_pwd == confirma_pwd and len(nova_pwd) >= 4:
                fracao = st.session_state['user_fracao']
                contactos_db[fracao]['password'] = nova_pwd
                contactos_db[fracao]['must_change'] = False
                salvar_contactos(contactos_db)
                registrar_acao("Alteração Obrigatória de Password", f"Utilizador {fracao} alterou a palavra-passe.")
                st.session_state['must_change'] = False
                st.success("Palavra-passe atualizada com sucesso!")
                st.rerun()
            else:
                st.error("As palavras-passe não coincidem ou são muito curtas.")
    st.stop()

# --- SIDEBAR DE NAVEGAÇÃO E PERFIL ---
nome_exibido = next(
    (info['nome'] for fracao, info in contactos_db.items()
     if info.get('email', '').lower() == st.session_state.get('user_email', '').lower()),
    "Administrador"
)
st.sidebar.title("🏢 Gestão Condomínio José Fontana N.º 2")
st.sidebar.markdown(f"### 👋 Olá, **{nome_exibido}**")
st.sidebar.markdown(f"📍 **Fracção:** {st.session_state['user_fracao']}")
st.sidebar.divider()

# --- SELECTOR DE MODO DE VISTA (Para perfis "Ambos") ---
perfilAtual = st.session_state.get('user_role', '')
if perfilAtual == "Ambos":
    st.sidebar.markdown("### ⚙️ Modo de Vista")
    modo_vista = st.sidebar.radio(
        "Select Mode:",
        ["Administrador", "Morador"],
        key="modo_vista_radio",
        horizontal=True
    )
else:
    modo_vista = perfilAtual

# --- NAVEGAÇÃO SEGÚN MODO ---
if modo_vista == "Administrador":
    menu = st.sidebar.radio("Navegação", ["📊 Visão Geral", "🏦 Movimentos", "🧾 Gastos", "📝 Actas", "📇 Condóminos", "🛡️ Auditoria"])
else:
    menu = st.sidebar.radio("Navegação", ["📊 O Meu Plano", "🧾 Recibos", "📝 Actas"])

df_movimentos = carregar_movimentos()
df_gastos = carregar_gastos()
actas_db = carregar_actas()

# --- VISTA ADMINISTRADOR ---
if menu == "📊 Visão Geral":
    st.title("📊 Visão Geral & Alertas 🚀")

    if not df_movimentos.empty and 'Data Mov' in df_movimentos.columns and df_movimentos['Data Mov'].notnull().any():
        data_min_mov = df_movimentos['Data Mov'].min().strftime('%d/%m/%Y')
        data_max_mov = df_movimentos['Data Mov'].max().strftime('%d/%m/%Y')
        periodo_str = f"Período: {data_min_mov} até {data_max_mov}"
    else:
        periodo_str = "Sem movimentos registados"
        data_max_mov = "N/A"
    saldo_atual = df_movimentos['Saldo (€)'].iloc[-1] if not df_movimentos.empty and 'Saldo (€)' in df_movimentos.columns else 0.0
    total_entradas = df_movimentos[df_movimentos['Valor (€)'] > 0]['Valor (€)'].sum() if not df_movimentos.empty and 'Valor (€)' in df_movimentos.columns else 0.0
    total_saidas = abs(df_movimentos[df_movimentos['Valor (€)'] < 0]['Valor (€)'].sum()) if not df_movimentos.empty and 'Valor (€)' in df_movimentos.columns else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Bancário Actual", f"{saldo_atual:.2f} €", delta=f"Ref. a {data_max_mov}")
    c2.metric("Total Entradas (Créditos)", f"{total_entradas:.2f} €", delta=periodo_str)
    c3.metric("Total Saídas (Débitos)", f"{total_saidas:.2f} €", delta=periodo_str)

    st.divider()
    st.subheader("🚨 Alertas de Conformidade e Faturas em Falta")

    despesas_totais = df_movimentos[df_movimentos['Valor (€)'] < 0] if not df_movimentos.empty else pd.DataFrame()
    despesas_conciliadas = despesas_totais[despesas_totais['Reconciliado'] == "Sim"] if not despesas_totais.empty else pd.DataFrame()

    def exige_fatura(row):
        fracao = str(row.get('Fracção Associada', ''))
        desc = str(row.get('Descrição', '')).lower()
        if fracao == "Administração do Condomínio":
            if "imposto de selo" in desc or "manutencao de conta" in desc or "comissao" in desc:
                return False
        return True

    if not despesas_conciliadas.empty:
        precisam_fatura = despesas_conciliadas[despesas_conciliadas.apply(exige_fatura, axis=1)]
        despesas_sem_fatura = precisam_fatura[
            precisam_fatura['Fatura_Despesa_ID'].isna() | (precisam_fatura['Fatura_Despesa_ID'] == "")
        ]
    else:
        despesas_sem_fatura = pd.DataFrame()

    if len(despesas_totais) == 0:
        st.info("Ainda não existem despesas (saídas) registadas no extrato.")
    elif len(despesas_conciliadas) == 0:
        st.warning(f"⚠️ Existem **{len(despesas_totais)}** despesas registadas, mas ainda nenhuma foi marcada como conciliada ('Sim').")
    elif not despesas_sem_fatura.empty:
        st.error(f"⚠️ Existem **{len(despesas_sem_fatura)}** despesas conciliadas que exigem fatura e estão sem comprovativo associado!")
        st.dataframe(despesas_sem_fatura[['Data Mov', 'Descrição', 'Valor (€)']], use_container_width=True)
    else:
        st.success("✅ Todas as despesas conciliadas que exigem fatura possuem o respetivo comprovativo associado.")

elif menu == "🏦 Movimentos":
    st.title("🏦 Gestão de Movimentos Bancários 🏦")

    uploaded_pdfs = st.file_uploader(
        "Selecione os ficheiros PDF do extrato bancário BPI (pode escolher vários)",
        type=["pdf"],
        accept_multiple_files=True
    )

    if uploaded_pdfs:
        if not isinstance(uploaded_pdfs, list):
            uploaded_pdfs = [uploaded_pdfs]

        st.info(f"Selecionou {len(uploaded_pdfs)} ficheiro(s). Prima o botão abaixo para processar todos.")
        if st.button("Processar Todos os Extratos PDF"):
            progress_bar = st.progress(0)
            status_container = st.empty()
            logs_processamento = []

            total_files = len(uploaded_pdfs)
            for idx, pdf_file in enumerate(uploaded_pdfs):
                status_container.write(f"⚡ A processar ficheiro {idx+1}/{total_files}: **{pdf_file.name}**...")
                try:
                    pdf_bytes = pdf_file.read()
                    texto_pdf = extrair_texto_pdf(pdf_bytes)
                    novos_movs = processar_extrato_bpi(texto_pdf)

                    if novos_movs:
                        df_novos = pd.DataFrame(novos_movs)
                        df_novos['Data Mov'] = pd.to_datetime(df_novos['Data Mov'], format='%d/%m/%Y', errors='coerce')
                        df_novos['Data Val'] = pd.to_datetime(df_novos['Data Val'], format='%d/%m/%Y', errors='coerce')

                        hashes_existentes = set(df_movimentos['Hash_Movimento'].dropna())
                        df_filtrado = df_novos[~df_novos['Hash_Movimento'].isin(hashes_existentes)]

                        if not df_filtrado.empty:
                            df_movimentos = pd.concat([df_movimentos, df_filtrado], ignore_index=True)
                            salvar_movimentos(df_movimentos)
                            logs_processamento.append(f"✅ **{pdf_file.name}**: {len(df_filtrado)} novos movimentos importados!")
                        else:
                            logs_processamento.append(f"⚠️ **{pdf_file.name}**: Todos os movimentos já estavam registados.")
                    else:
                        logs_processamento.append(f"❌ **{pdf_file.name}**: Não foi possível extrair dados de texto.")
                except Exception as e:
                    logs_processamento.append(f"❌ **{pdf_file.name}**: Erro inesperado: {e}")

                progress_bar.progress((idx + 1) / total_files)

            status_container.empty()
            st.success("✨ Processamento em lote concluído!")
            for log in logs_processamento:
                st.markdown(log)

            registrar_acao("Importação Extratos", f"Processados {total_files} ficheiros PDF.")
            backup_automatico()
            st.rerun()

    st.divider()
    st.subheader("Gestão e Reconciliação de Movimentos Bancários")

    filtro_tempo = st.selectbox(
        "Filtrar Período de Visualização de Movimentos:",
        ["Últimos 12 Meses", "Ano Corrente (2026)", "Ano 2025", "Todo o Histórico Registado"]
    )

    df_display = df_movimentos.copy()
    if not df_display.empty and 'Data Mov' in df_display.columns:
        data_maxima = df_display['Data Mov'].max()
        if filtro_tempo == "Últimos 12 Meses" and pd.notnull(data_maxima):
            limite_data = data_maxima - pd.DateOffset(months=12)
            df_display = df_display[df_display['Data Mov'] >= limite_data]
        elif filtro_tempo == "Ano Corrente (2026)":
            df_display = df_display[df_display['Data Mov'].dt.year == 2026]
        elif filtro_tempo == "Ano 2025":
            df_display = df_display[df_display['Data Mov'].dt.year == 2025]

    cols_to_show = [col for col in df_display.columns if 'hash' not in col.lower()]
    df_visual = df_display[cols_to_show]

    st.markdown(f"**A apresentar {len(df_visual)} movimentos bancários:**")
    st.dataframe(df_visual, use_container_width=True)

    st.subheader("✏️ Associar Fracção, Administração, Quotas ou Faturas")
    if not df_movimentos.empty:
        mov_ids = df_movimentos.index.tolist()

        def format_mov_option(x):
            row = df_movimentos.loc[x]
            data_str = row['Data Mov'].strftime('%d/%m/%Y') if pd.notnull(row['Data Mov']) else ''
            status_icon = "✅ [Conciliado]" if row.get('Reconciliado') == "Sim" else "⏳ [Pendente]"
            frac_str = f"({row.get('Fracção Associada', 'Não Identificada')})" if row.get('Reconciliado') == "Sim" else ""
            return f"{status_icon} Data: {data_str} | {row['Descrição']} | {row['Valor (€)']} € {frac_str}"

        selected_idx = st.selectbox(
            "Selecione a linha do movimento para reconciliar/editar:",
            mov_ids,
            format_func=format_mov_option
        )

        row_sel = df_movimentos.loc[selected_idx]
        st.info(f"Movimento Selecionado: **{row_sel['Descrição']}** ({row_sel['Valor (€)']} €)")

        with st.form("form_reconciliar"):
            c_frac, c_mes, c_rec = st.columns([2, 3, 1])

            lista_fracoes = ["Não Identificada", "Administração do Condomínio"] + [f for f in contactos_db.keys() if f != "Administração do Condomínio"]

            valor_fracao = str(row_sel.get('Fracção Associada', 'Não Identificada'))
            if valor_fracao in lista_fracoes:
                fracAtual = valor_fracao
            else:
                fracAtual = "Não Identificada"

            index_frac = lista_fracoes.index(fracAtual) if fracAtual in lista_fracoes else 0
            nova_fracao = c_frac.selectbox("Atribuir a Fracção / Administração", lista_fracoes, index=index_frac)

            opcoes_meses = [f"{ano}-{mes:02d}" for ano in range(2025, 2028) for mes in range(1, 13)]
            meses_atuais = [m.strip() for m in str(row_sel.get('Mes_Ano_Quota', '') or '').split(',') if m.strip() in opcoes_meses]
            novos_meses = c_mes.multiselect("Meses de Quota Associados (se aplicável):", opcoes_meses, default=meses_atuais)

            nova_fatura_id = None
            if row_sel['Valor (€)'] < 0:
                st.markdown("---")
                st.markdown("🧾 **Vincular Fatura / Despesa Registada:**")
                lista_faturas_opcoes = ["Nenhuma / Não Aplicável"]
                if not df_gastos.empty:
                    for _, g_row in df_gastos.iterrows():
                        lista_faturas_opcoes.append(f"{g_row['ID']} - {g_row.get('Fornecedor', 'N/A')} ({g_row['Valor (€)']} €)")

                fatAtual_id = row_sel.get('Fatura_Despesa_ID')
                default_fat_idx = 0
                if pd.notnull(fatAtual_id) and fatAtual_id != "":
                    for idx_f, opt in enumerate(lista_faturas_opcoes):
                        if opt.startswith(str(fatAtual_id)):
                            default_fat_idx = idx_f
                            break

                sel_fat_opt = st.selectbox("Selecione a Fatura correspondente a este gasto:", lista_faturas_opcoes, index=default_fat_idx)
                if sel_fat_opt != "Nenhuma / Não Aplicável":
                    nova_fatura_id = sel_fat_opt.split(" - ")[0]

            novo_status = c_rec.selectbox("Reconciliado", ["Sim", "Não"], index=0 if row_sel['Reconciliado'] == "Sim" else 1)

            btn_salvar_rec = st.form_submit_button("Gravar Alterações de Reconciliação")

            if btn_salvar_rec:
                df_movimentos.loc[selected_idx, 'Fracção Associada'] = nova_fracao
                df_movimentos.loc[selected_idx, 'Mes_Ano_Quota'] = ", ".join(novos_meses) if novos_meses else None
                df_movimentos.loc[selected_idx, 'Reconciliado'] = novo_status

                if novo_status == "Sim":
                    info_admin_validacao = obter_info_admin()
                    df_movimentos.loc[selected_idx, 'Administrador Validador'] = info_admin_validacao['nome']
                else:
                    df_movimentos.loc[selected_idx, 'Administrador Validador'] = None

                if row_sel['Valor (€)'] < 0:
                    df_movimentos.loc[selected_idx, 'Fatura_Despesa_ID'] = nova_fatura_id
                    if nova_fatura_id and not df_gastos.empty and 'ID' in df_gastos.columns:
                        hash_m = row_sel.get('Hash_Movimento', '')
                        df_gastos.loc[df_gastos['ID'] == nova_fatura_id, 'Hash_Movimento'] = hash_m
                        salvar_gastos(df_gastos)

                salvar_movimentos(df_movimentos)
                registrar_acao("Conciliação Bancária", f"Conciliado movimento de {row_sel['Valor (€)']} € para {nova_fracao} (Fatura: {nova_fatura_id}).")
                backup_automatico()
                st.success("Reconciliação e associação de fatura atualizadas com sucesso!")
                st.rerun()

elif menu == "🧾 Gastos":
    st.title("🧾 Gastos e Faturas 🧾")
    st.subheader("🧾 Registo e Anexo de Faturas de Gastos")
    with st.form("form_registo_gasto"):
        cg0, cg1, cg2, cg3 = st.columns([2, 2, 3, 2])
        num_fatura_input = cg0.text_input("N.º da Fatura / Recibo (Ex: FT 2026/123)", placeholder="Obrigatório")
        data_gasto = cg1.date_input("Data da Fatura", datetime.now())
        fornecedor = cg2.text_input("Fornecedor / Entidade")
        valor_gasto = cg3.number_input("Valor (€)", min_value=0.0, step=0.01)

        descr_gasto = st.text_input("Descrição da Despesa")
        categoria = st.selectbox("Categoria de Despesa", ["Eletricidade", "Limpeza", "Manutenção", "Seguro", "Comissões Bancárias", "Outros"])

        movs_exit = df_movimentos[df_movimentos['Valor (€)'] < 0] if not df_movimentos.empty else pd.DataFrame()
        lista_mov_opcoes = ["Nenhum / Associar depois"]
        if not movs_exit.empty:
            for idx_m, m_row in movs_exit.iterrows():
                d_mov = m_row['Data Mov'].strftime('%d/%m/%Y') if pd.notnull(m_row['Data Mov']) else ''
                lista_mov_opcoes.append(f"Índice {idx_m} | Data: {d_mov} | {m_row['Descrição']} ({m_row['Valor (€)']} €)")

        assoc_mov_escolha = st.selectbox("Vincular diretamente a um Movimento Bancário de Saída (Opcional):", lista_mov_opcoes)

        ficheiro_fatura = st.file_uploader("Ficheiro da Fatura (PDF / JPG / PNG)", type=["pdf", "jpg", "jpeg", "png"])

        btn_guardar_gasto = st.form_submit_button("Guardar Fatura / Despesa")

        if btn_guardar_gasto:
            if not num_fatura_input.strip():
                st.error("❌ Por favor, introduza o número da fatura/recibo.")
            else:
                fatura_id = num_fatura_input.strip()
                if not df_gastos.empty and 'ID' in df_gastos.columns and fatura_id in df_gastos['ID'].values:
                    st.error(f"❌ Já existe uma fatura registada com o número '{fatura_id}'. Utilize um número único.")
                else:
                    nome_ficheiro = ""
                    if ficheiro_fatura is not None:
                        nome_ficheiro = f"{fatura_id.replace('/', '_')}_{ficheiro_fatura.name}"
                        os.makedirs(DIR_ANEXOS, exist_ok=True)
                        with open(os.path.join(DIR_ANEXOS, nome_ficheiro), "wb") as f:
                            f.write(ficheiro_fatura.read())

                    hash_vinculado = ""
                    if assoc_mov_escolha != "Nenhum / Associar depois":
                        try:
                            idx_str = assoc_mov_escolha.split(" | ")[0].replace("Índice ", "").strip()
                            mov_idx = int(idx_str)
                            hash_vinculado = df_movimentos.loc[mov_idx, 'Hash_Movimento']
                            df_movimentos.loc[mov_idx, 'Fatura_Despesa_ID'] = fatura_id
                            df_movimentos.loc[mov_idx, 'Fracção Associada'] = "Administração do Condomínio"
                            df_movimentos.loc[mov_idx, 'Reconciliado'] = "Sim"
                            info_admin_vinc = obter_info_admin()
                            df_movimentos.loc[mov_idx, 'Administrador Validador'] = info_admin_vinc['nome']
                            salvar_movimentos(df_movimentos)
                        except Exception as e:
                            print(f"Erro ao vincular movimento: {e}")
                    nova_linha_gasto = {
                        "ID": fatura_id,
                        "Data": data_gasto.strftime("%Y-%m-%d"),
                        "Fornecedor": fornecedor,
                        "Descrição": descr_gasto,
                        "Valor (€)": valor_gasto,
                        "Categoria": categoria,
                        "Nome_Ficheiro": nome_ficheiro,
                        "Hash_Movimento": hash_vinculado
                    }
                    df_gastos = pd.concat([df_gastos, pd.DataFrame([nova_linha_gasto])], ignore_index=True)
                    salvar_gastos(df_gastos)
                    registrar_acao("Registo de Gasto", f"Adicionada fatura '{fatura_id}' de {valor_gasto} €.")
                    backup_automatico()
                    st.success(f"Fatura '{fatura_id}' registada com sucesso!")
                    st.rerun()

    st.divider()
    st.subheader("Faturas Registadas no Sistema")
    st.dataframe(df_gastos, use_container_width=True)

elif menu == "📝 Actas":
    st.title("📝 Actas de Assembleia 📝")
    st.subheader("📝 Módulo de Actas da Assembleia")
    with st.form("form_acta"):
        ca1, ca2 = st.columns(2)
        num_acta = ca1.text_input("Número / Título da Acta")
        data_acta = ca2.date_input("Data da Reunião", datetime.now())
        conteudo_transcicao = st.text_area("Transcrição Completa ou Resumo da Acta", height=150)
        anexo_acta = st.file_uploader("Anexo em PDF/Imagem da Acta Assinada", type=["pdf", "jpg", "png"])

        btn_salvar_acta = st.form_submit_button("Registar Acta")
        if btn_salvar_acta:
            nome_anexo = ""
            if anexo_acta is not None:
                nome_anexo = f"Acta_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{anexo_acta.name}"
                os.makedirs(DIR_ACTAS, exist_ok=True)
                with open(os.path.join(DIR_ACTAS, nome_anexo), "wb") as f:
                    f.write(anexo_acta.read())

            nova_acta = {
                "id": len(actas_db) + 1,
                "titulo": num_acta,
                "data": data_acta.strftime("%Y-%m-%d"),
                "texto": conteudo_transcicao,
                "anexo": nome_anexo
            }
            actas_db.append(nova_acta)
            salvar_actas(actas_db)
            registrar_acao("Registo de Acta", f"Adicionada acta: {num_acta}.")
            backup_automatico()
            st.success("Acta guardada com sucesso!")
            st.rerun()

    st.divider()
    st.subheader("Actas Registadas")
    for acta in actas_db:
        with st.expander(f"📌 {acta['titulo']} - Data: {acta['data']}"):
            st.write(acta['texto'])
            if acta.get('anexo'):
                st.info(f"Ficheiro Anexo: {acta['anexo']}")

elif menu == "📇 Condóminos":
    st.title("📇 Gestão de Condóminos 📇")
    st.subheader("📇 Gestão de Condóminos e Credenciais de Acesso")
    st.info("💡 **Dica:** Pode editar diretamente na tabela abaixo.")

    rows_contactos = []
    for fracao, info in contactos_db.items():
        if fracao == "Administração do Condomínio":
            continue
        rows_contactos.append({
            "Fracção": fracao,
            "Nome do Titular": info.get('nome', ''),
            "Telemóvel": info.get('telemovel', ''),
            "E-mail": info.get('email', ''),
            "NIF": info.get('nif', ''),
            "Quota Mensal (€)": info.get('quota', 15.0),
            "Perfil": info.get('perfil', 'Morador')
        })

    df_contactos_editavel = pd.DataFrame(rows_contactos)

    df_editado = st.data_editor(
        df_contactos_editavel,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Fracção": st.column_config.TextColumn("Fracção", required=True),
            "Nome do Titular": st.column_config.TextColumn("Nome do Titular", required=True),
            "Telemóvel": st.column_config.TextColumn("Telemóvel"),
            "E-mail": st.column_config.TextColumn("E-mail", required=True),
            "NIF": st.column_config.TextColumn("NIF"),
            "Quota Mensal (€)": st.column_config.NumberColumn("Quota Mensal (€)", min_value=0.0, format="%.2f"),
            "Perfil": st.column_config.SelectboxColumn("Perfil", options=["Morador", "Ambos", "Administrador"], required=True)
        }
    )

    st.divider()
    btn_salvar_edicao = st.button("💾 Guardar Alterações na Tabela de Condóminos")

    if btn_salvar_edicao:
        fraccoes_novas = df_editado["Fracção"].tolist()
        if len(fraccoes_novas) != len(set(fraccoes_novas)):
            st.error("❌ Erro: Existem fracções duplicadas.")
        else:
            novo_contactos_db = {"Administração do Condomínio": contactos_db.get("Administração do Condomínio", CONTACTOS_INICIAIS["Administração do Condomínio"])}
            for _, row in df_editado.iterrows():
                fracao_key = str(row["Fracção"]).strip()
                pwd_actual = contactos_db.get(fracao_key, {}).get('password', 'fontana2')
                must_change_actual = contactos_db.get(fracao_key, {}).get('must_change', False)

                novo_contactos_db[fracao_key] = {
                    "nome": row["Nome do Titular"],
                    "email": row["E-mail"],
                    "telemovel": row["Telemóvel"],
                    "nif": row["NIF"],
                    "quota": float(row["Quota Mensal (€)"]),
                    "perfil": row["Perfil"],
                    "password": pwd_actual,
                    "must_change": must_change_actual
                }

            contactos_db = novo_contactos_db
            salvar_contactos(contactos_db)
            registrar_acao("Edição de Condóminos", "Actualização da tabela de condóminos.")
            backup_automatico()
            st.success("✅ Condóminos atualizados com sucesso!")
            st.rerun()

    st.divider()
    st.subheader("🔑 Redefinir Palavra-passe de um Condómino")
    with st.form("form_reset_pwd"):
        fracao_target = st.selectbox("Selecione a Fracção:", [f for f in contactos_db.keys() if f != "Administração do Condomínio"])
        nova_temp_pwd = st.text_input("Nova Palavra-passe Temporária", value="fontana2")
        btn_reset = st.form_submit_button("Resetar Palavra-passe e Forçar Alteração")

        if btn_reset:
            contactos_db[fracao_target]['password'] = nova_temp_pwd
            contactos_db[fracao_target]['must_change'] = True
            salvar_contactos(contactos_db)
            registrar_acao("Reset de Password", f"Palavra-passe redefinida para {fracao_target}.")
            backup_automatico()
            st.success(f"Palavra-passe de {fracao_target} redefinida com sucesso.")

elif menu == "🛡️ Auditoria":
    st.title("🛡️ Auditoria & Backups 🛡️")
    st.subheader("🛡️ Auditoria & Backups do Sistema")

    st.markdown("### 📥 Criar e Transferir Cópia de Segurança")
    st.write("Transfira um ficheiro `.zip` com todos os dados da base de dados e anexos antes de realizar atualizações.")

    zip_buffer = gerar_backup_zip()
    data_zip = zip_buffer.read()

    st.download_button(
        label="⬇️ Transferir Backup Completo (.zip)",
        data=data_zip,
        file_name=f"Backup_Condominio_Fontana2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        mime="application/zip",
        use_container_width=True
    )

    st.divider()
    st.markdown("### 🔄 Restaurar / Transferir Backup (Fusão Inteligente)")
    st.warning("⚠️ **Atenção:** Ao enviar um backup anterior `.zip`, o sistema fará uma **validação e fusão inteligente (Merge)**.")
    backup_submetido = st.file_uploader("Selecione o ficheiro `.zip` do backup para restaurar", type=["zip"])
    if backup_submetido is not None:
        if st.button("🚀 Processar e Fundir Dados do Backup"):
            with st.spinner("A analisar e a restaurar dados em segurança..."):
                sucesso, relatorio = restaurar_backup_zip(backup_submetido)
                if sucesso:
                    st.success("✅ Restauro e fusão concluídos com sucesso!")
                    st.markdown("**Relatório da Fusão:**")
                    for linha in relatorio:
                        st.write(f"- {linha}")
                    registrar_acao("Restauro de Backup", "Importação e fusão bem-sucedida de ficheiro ZIP de backup.")
                    backup_automatico()
                else:
                    st.error("❌ Ocorreu um erro ao restaurar o backup.")
                    for erro in relatorio:
                        st.error(erro)

    st.divider()
    st.subheader("📋 Diário de Auditoria")
    logs = carregar_logs()
    st.write(f"Total de entradas registradas no diário de auditoria: **{len(logs)}**")

    if logs:
        df_logs = pd.DataFrame(logs)
        st.dataframe(df_logs.sort_values(by="timestamp", ascending=False), use_container_width=True)

        csv_logs = df_logs.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Transferir Historial de Auditoria (CSV)",
            data=csv_logs,
            file_name=f"auditoria_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("Ainda não foram registradas actividades no sistema.")

# --- VISTA MORADOR / CONDÓMINO ---
# --- VISTA MORADOR / CONDÓMINO ---
else:
    fracao_user = st.session_state['user_fracao']
    st.title(f"🏠 Portal do Condómino - Fracção {fracao_user}")

    # Inicializar estado da navegação
    if 'morador_menu_option' not in st.session_state: st.session_state['morador_menu_option'] = "📊 O Meu Plano"
    
    # Se houver um pedido de jump_to_mes ativo, força a navegação para "🧾 Recibos"
    if st.session_state.get('jump_to_mes'):
        st.session_state['morador_menu_option'] = "🧾 Recibos"

    menu_morador = st.radio(
        "Navegação Morador",
        ["📊 O Meu Plano", "🧾 Recibos", "📝 Actas"],
        key="morador_menu_option",
        horizontal=True,
        label_visibility="collapsed"
    )

    if menu_morador == "📊 O Meu Plano":
        st.subheader("Estado de Pagamento das Quotas Mensais")
        st.info("💡 **Dica:** Clique no botão de um mês pago (verde) para abrir e emitir o recibo correspondente.")
        
        # Gerar os últimos 24 meses
        meses_24 = []
        data_ref = datetime.now()
        for i in range(24):
            mes = data_ref.month - i; ano = data_ref.year
            while mes <= 0: mes += 12; ano -= 1
            meses_24.append(f"{ano}-{mes:02d}")
        meses_24.reverse()

        # CSS para forçar altura e largura igual em todos os botões
        st.markdown("""<style>.stButton button {width: 100%; height: 60px;}</style>""", unsafe_allow_html=True)
        
        cols = st.columns(6)
        for idx, m_str in enumerate(meses_24):
            pago = False
            # Verifica se existe algum movimento reconciliado para este mês e fração
            if not df_movimentos.empty:
                movs_fracao = df_movimentos[(df_movimentos['Fracção Associada'] == fracao_user) & (df_movimentos['Valor (€)'] > 0)]
                for _, r in movs_fracao.iterrows():
                    if m_str in str(r.get('Mes_Ano_Quota', '')): pago = True; break
            
            # Botão clicável se estiver pago, caso contrário mostra erro
            if pago:
                if cols[idx % 6].button(f"✅ {m_str}\nPago", key=f"btn_{m_str}"):
                    st.session_state['jump_to_mes'] = m_str
                    st.rerun()
            else:
                cols[idx % 6].error(f"❌ {m_str}\nPendente")

    elif menu_morador == "🧾 Recibos":
        st.subheader("🧾 Emitir e Transferir Recibo de Quotas")
        movs_recibos = df_movimentos[(df_movimentos['Fracção Associada'] == fracao_user) & (df_movimentos['Valor (€)'] > 0)]
        
        if not movs_recibos.empty:
            mes_pre = st.session_state.get('jump_to_mes')
            options = movs_recibos.index.tolist()
            default_idx = 0
            
            # Tenta encontrar o índice da transação correspondente ao mês solicitado
            if mes_pre:
                for i, idx in enumerate(options):
                    if mes_pre in str(df_movimentos.loc[idx, 'Mes_Ano_Quota']): 
                        default_idx = i; break
                st.session_state['jump_to_mes'] = None # Reset após navegação
            
            # Selectbox seguro que utiliza o índice da lista de opções
            sel_idx = st.selectbox(
                "Selecione a Transação de Pagamento:", 
                options, 
                index=default_idx, 
                format_func=lambda x: f"{df_movimentos.loc[x, 'Data Mov'].strftime('%d/%m/%Y') if pd.notnull(df_movimentos.loc[x, 'Data Mov']) else 'N/A'} | {df_movimentos.loc[x, 'Valor (€)']} € | {df_movimentos.loc[x, 'Mes_Ano_Quota']}"
            )
            
            mov_sel = df_movimentos.loc[sel_idx]
            info_prop = contactos_db.get(fracao_user, {})
            
            # Identificar validador
            info_admin = obter_info_admin()
            
            dados = {
                'ref_id': mov_sel.get('Hash_Movimento', str(sel_idx))[:8].upper(), 
                'data_emissao': datetime.now().strftime('%d/%m/%Y'), 
                'fracao': fracao_user, 
                'titular': info_prop.get('nome', 'Condómino'), 
                'nif': info_prop.get('nif', 'N/A'), 
                'valor': mov_sel['Valor (€)'], 
                'meses_pagos': mov_sel.get('Mes_Ano_Quota', 'Quota Regular'), 
                'data_processamento': mov_sel['Data Val'].strftime('%d/%m/%Y') if pd.notnull(mov_sel['Data Val']) else 'N/A', 
                'conta_bancaria': '9-3085758-000-001'
            }
            
            pdf = gerar_recibo_pdf(dados, info_admin)
            st.download_button("📥 Transferir Recibo (PDF)", data=pdf, file_name=f"Recibo_{dados['ref_id']}.pdf", mime="application/pdf", use_container_width=True)
        else:
            st.info("Não existem pagamentos registados para esta fracção.")

    elif menu_morador == "📝 Actas":
        st.subheader("📝 Consulta de Actas das Assembleias")
        if actas_db:
            for acta in actas_db:
                with st.expander(f"📌 {acta['titulo']} - {acta['data']}"):
                    st.write(acta.get('texto', ''))
                    if acta.get('anexo'):
                        caminho = os.path.join(DIR_ACTAS, acta['anexo'])
                        if os.path.exists(caminho):
                            with open(caminho, "rb") as f: 
                                st.download_button(f"📥 {acta['anexo']}", data=f.read(), file_name=acta['anexo'])
        else:
            st.info("Ainda não existem actas disponibilizadas.")

# --- FOOTER GLOBAL ---
st.sidebar.divider()
if st.sidebar.button("Terminar Sessão 🚪"):
    registrar_acao("Logout", f"O utilizador {st.session_state['user_email']} terminou a sessão.")
    st.session_state['authenticated'] = False
    st.rerun()
