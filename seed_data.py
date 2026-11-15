import random
from datetime import datetime, timedelta
import pandas as pd
import bcrypt

def gerar_hash_bcrypt(senha_plana: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(senha_plana.encode("utf-8"), salt).decode("utf-8")

def gerar_base_alunos(caminho_arquivo: str = "alunos_maisvida.csv", total: int = 500):
    nomes = [
        "João da Silva", "Maria Oliveira", "Carlos Eduardo", "Ana Beatriz",
        "Pedro Henrique", "Fernanda Lima", "Lucas Martins", "Juliana Costa",
        "Rafael Almeida", "Larissa Oliveira", "Bruno Souza", "Camila Rocha",
        "Thiago Ribeiro", "Patrícia Gomes", "Gabriel Carvalho", "Aline Dias",
        "Rodrigo Santana", "Beatriz Mendes", "Felipe Castro", "Vanessa Cardoso"
    ]
    modalidades = ["Futevôlei", "Vôlei de Praia", "Funcional"]
    pesos_mod = [0.50, 0.30, 0.20]

    horarios = ["06:00", "07:00", "08:00", "09:00", "17:00", "18:00", "19:00", "20:00"]
    # Horários de pico (07h, 08h, 18h, 19h) mais cheios para destacar no gráfico
    pesos_hor = [0.10, 0.18, 0.15, 0.07, 0.08, 0.18, 0.16, 0.08]

    vinculos = ["Mensalista", "Gympass", "Totalpass", "Aula Experimental"]
    pesos_vinc = [0.40, 0.30, 0.20, 0.10]

    hoje = datetime.now()
    registros = []

    for i in range(1, total + 1):
        data_cadastro = hoje - timedelta(days=random.randint(1, 120), hours=random.randint(1, 12))
        nome = f"{random.choice(nomes)} ({i:03d})"

        # Primeiros 4 alunos fazem aniversário HOJE; próximos 6 fazem nos próximos 7 dias
        if i <= 4:
            ano_nasc = random.randint(1980, 2004)
            data_nasc = hoje.replace(year=ano_nasc).strftime("%d/%m/%Y")
        elif i <= 10:
            data_aniv = hoje + timedelta(days=random.randint(1, 6))
            ano_nasc = random.randint(1980, 2004)
            data_nasc = data_aniv.replace(year=ano_nasc).strftime("%d/%m/%Y")
        else:
            ano_nasc = random.randint(1968, 2006)
            mes_nasc = random.randint(1, 12)
            dia_nasc = random.randint(1, 28)
            data_nasc = f"{dia_nasc:02d}/{mes_nasc:02d}/{ano_nasc}"

        registros.append({
            "ID_Aluno": i,
            "Data_Cadastro": data_cadastro.strftime("%d/%m/%Y %H:%M:%S"),
            "Nome_Completo": nome,
            "Data_Nascimento": data_nasc,
            "Contato_WhatsApp": f"219{random.randint(80000000, 99999999)}",
            "Modalidade": random.choices(modalidades, weights=pesos_mod, k=1)[0],
            "Horario_Treino": random.choices(horarios, weights=pesos_hor, k=1)[0],
            "Tipo_Vinculo": random.choices(vinculos, weights=pesos_vinc, k=1)[0],
            "Status": "Ativo"
        })

    df = pd.DataFrame(registros)
    df.to_csv(caminho_arquivo, index=False, encoding="utf-8")
    print(f"[OK] Base '{caminho_arquivo}' criada com {len(df)} alunos cadastrados.")

if __name__ == "__main__":
    gerar_base_alunos()