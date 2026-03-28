import streamlit as st
import pandas as pd
import io
import datetime # Para pegar a data atual automaticamente nos formulários

# Configuração da página do Streamlit
st.set_page_config(page_title="Gestão de Vinhos", page_icon="🍷", layout="wide")

st.title("🍷 Sistema de Gestão de Vinhos")
st.markdown("Adega Cecília")

# --- 0. INICIALIZAÇÃO DA SESSÃO (MEMÓRIA DO APP) ---
# Como queremos zerar as compras e vendas e adicionar manualmente, 
# criamos tabelas vazias na "memória" do Streamlit.
if 'compras' not in st.session_state:
    st.session_state['compras'] = pd.DataFrame(columns=['Data', 'Fornecedor', 'Vinho', 'Qtd', 'Preço Unitário (R$)', 'Custo Total (R$)'])

if 'vendas' not in st.session_state:
    st.session_state['vendas'] = pd.DataFrame(columns=['Vinho', 'Qtd', 'Data', 'Cliente', 'Preço Venda Unit. (R$)', 'Receita Total (R$)', 'Custo Unitário Base (R$)', 'Lucro (R$)'])

# Memória temporária para ir guardando os vinhos de um lote antes de salvar de uma vez
if 'lote_atual' not in st.session_state:
    st.session_state['lote_atual'] = []

# --- 1. CARREGAMENTO DOS DADOS ---
# Agora carregamos apenas o Estoque Inicial
@st.cache_data
def carregar_estoque_inicial():
    try:
        # Lê o seu arquivo local
        df_estoque = pd.read_csv('loja - Estoque.csv')
    except FileNotFoundError:
        # Exemplo de fallback caso o arquivo não seja encontrado na hora de testar
        csv_estoque = """Vinho,Estoque Inicial,Status\nChandon Brut,2,M&A\nEl Enemigo Chardonnay,3,M&A"""
        df_estoque = pd.read_csv(io.StringIO(csv_estoque))
    return df_estoque

df_estoque = carregar_estoque_inicial()
# Em vez de ler do CSV, puxamos as tabelas em branco da memória da sessão
df_compras = st.session_state['compras']
df_vendas = st.session_state['vendas']

# --- 2. PROCESSAMENTO E LÓGICA DE NEGÓCIO ---
# Agrupar compras por vinho (Soma total de garrafas compradas de cada rótulo)
compras_agrupadas = df_compras.groupby('Vinho')['Qtd'].sum().reset_index()
compras_agrupadas.rename(columns={'Qtd': 'Total Comprado'}, inplace=True)

# Agrupar vendas por vinho
vendas_agrupadas = df_vendas.groupby('Vinho')['Qtd'].sum().reset_index()
vendas_agrupadas.rename(columns={'Qtd': 'Total Vendido'}, inplace=True)

# Juntar (Merge) as tabelas para calcular o Saldo (O que sua planilha "Saldo.csv" faz manualmente)
df_saldo = pd.merge(df_estoque[['Vinho', 'Estoque Inicial']], compras_agrupadas, on='Vinho', how='left')
df_saldo = pd.merge(df_saldo, vendas_agrupadas, on='Vinho', how='left')

# Preencher os vazios (NaN) com zero, caso um vinho não tenha tido venda ou compra
df_saldo.fillna(0, inplace=True)

# Calcular o Estoque Atual
df_saldo['Estoque Atual'] = df_saldo['Estoque Inicial'] + df_saldo['Total Comprado'] - df_saldo['Total Vendido']

# --- 3. INTERFACE VISUAL (DASHBOARD) ---

# Criando abas para organização
tab1, tab2, tab3 = st.tabs(["📊 Visão Geral", "🛒 Movimentações", "📈 Simulações"])

with tab1:
    st.subheader("Resumo do Estoque Atual")
    
    # Exibir métricas principais (Convertidas para Caixas)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Rótulos (Tipos de Vinho)", len(df_saldo))
    col2.metric("Total no Estoque (Caixas)", f"{(df_saldo['Estoque Atual'].sum()):.1f} cx")
    col3.metric("Total Vendido (Caixas)", f"{(df_saldo['Total Vendido'].sum()):.1f} cx")
    
    st.divider()
    st.subheader("📈 Desempenho de Vendas & Lucro")
    
    # Converter a coluna de Data para datetime para podermos filtrar o período
    df_v = st.session_state['vendas'].copy()
    if not df_v.empty:
        # Converte a data formatada para um objeto de tempo do Pandas
        df_v['Data_dt'] = pd.to_datetime(df_v['Data'], format="%d/%m/%Y", errors='coerce')
        
        # Seleção de Período com Calendário
        st.markdown("##### 📅 Filtrar Período")
        col_cal1, col_cal2 = st.columns(2)
        # Por padrão, mostra do dia 1º do mês atual até hoje
        hoje = datetime.date.today()
        primeiro_dia_mes = hoje.replace(day=1)
        
        start_date = col_cal1.date_input("Data Inicial", primeiro_dia_mes)
        end_date = col_cal2.date_input("Data Final", hoje)
        
        # Filtra as vendas no período selecionado
        mask = (df_v['Data_dt'].dt.date >= start_date) & (df_v['Data_dt'].dt.date <= end_date)
        vendas_periodo = df_v[mask]
        
        # Cálculos do período
        caixas = vendas_periodo['Qtd'].sum() if not vendas_periodo.empty else 0
        lucro_total = vendas_periodo['Lucro (R$)'].sum() if not vendas_periodo.empty else 0
        lucro_por_caixa = (lucro_total / caixas) if caixas > 0 else 0
        
        # Exibição das métricas
        st.markdown(f"**Resultados de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}:**")
        col_d1, col_d2, col_d3 = st.columns(3)
        col_d1.metric("📦 Caixas Vendidas", f"{caixas:.1f} cx")
        col_d2.metric("💰 Lucro Total", f"R$ {lucro_total:,.2f}")
        col_d3.metric("📊 Lucro Médio por Caixa", f"R$ {lucro_por_caixa:,.2f}")
    else:
        st.info("Registre algumas vendas na aba 'Movimentações' para ver os indicadores de desempenho de caixas e lucro!")
        
    st.divider()
    
    # Exibir tabela de saldo formatada
    st.dataframe(
        df_saldo.style.format({
            'Estoque Inicial': '{:.0f}',
            'Total Comprado': '{:.0f}',
            'Total Vendido': '{:.0f}',
            'Estoque Atual': '{:.0f}'
        }),
        use_container_width=True
    )
    
    # Gráfico simples de estoque atual por Vinho
    st.subheader("Estoque Atual por Rótulo (em caixas)")
    st.bar_chart(df_saldo.set_index('Vinho')['Estoque Atual'])

with tab2:
    st.subheader("Registrar Novas Movimentações")
    
    # Para não ficar confuso, separamos as Entradas e Saídas em sub-abas
    tab_compra, tab_venda = st.tabs(["🛒 Compras (Entrada em Lote)", "📤 Vendas (Saídas)"])
    
    with tab_compra:
        st.markdown("### 📥 Registrar Novo Lote")
        
        # Dados gerais da nota/lote
        col_info1, col_info2 = st.columns(2)
        data_c = col_info1.date_input("Data da Compra", datetime.date.today())
        fornecedor = col_info2.text_input("Fornecedor", placeholder="Ex: Márcia")
        
        st.markdown("#### 1. Adicionar Vinhos ao Lote")
        with st.form("form_item_lote", clear_on_submit=True):
            col_a, col_b, col_c = st.columns([2, 1, 1])
            vinho_c = col_a.selectbox("Vinho", df_estoque['Vinho'].unique())
            qtd_c = col_b.number_input("Qtd", min_value=1, step=1)
            preco_u = col_c.number_input("Preço por Caixa (R$)", min_value=0.0, step=5.0, format="%.2f", value=None, placeholder="0,00")
            
            if st.form_submit_button("Adicionar ao Lote"):
                if preco_u is None:
                    st.error("⚠️ Preencha o preço antes de adicionar!")
                else:
                    st.session_state['lote_atual'].append({
                        'Vinho': vinho_c,
                        'Qtd': qtd_c,
                        'Preço por Caixa (R$)': preco_u,
                        'Custo Total (R$)': qtd_c * preco_u
                    })
                    st.rerun()
        
        # Mostrar os itens que já estão no lote atual
        if len(st.session_state['lote_atual']) > 0:
            st.write("📋 **Itens no Lote Atual:**")
            
            # Loop para mostrar cada item com um botão de excluir ao lado
            for i, item in enumerate(st.session_state['lote_atual']):
                c1, c2, c3 = st.columns([4, 2, 1])
                c1.write(f"🍷 **{item['Vinho']}** ({item['Qtd']} un. a R$ {item['Preço Unitário (R$)']:.2f})")
                c2.write(f"Subtotal: R$ {item['Custo Total (R$)']:.2f}")
                if c3.button("❌", key=f"del_lote_{i}", help="Excluir este vinho do lote"):
                    st.session_state['lote_atual'].pop(i)
                    st.rerun()
            
            df_lote = pd.DataFrame(st.session_state['lote_atual'])
            
            # Resumo financeiro e de quantidade
            total_qtd = df_lote['Qtd'].sum()
            total_custo = df_lote['Custo Total (R$)'].sum()
            total_custo_frete = total_qtd * 90
            
            col_tot1, col_tot2 = st.columns(2)
            col_tot1.metric("Total de Caixas no Lote", total_qtd)
            col_tot2.metric("Valor Total do Lote + Frete", f"R\$ {total_custo:,.2f}" " + " f"R\$ {total_custo_frete:,.2f}")
            
            st.markdown("#### 2. Confirmar Lote")
            col_btn1, col_btn2 = st.columns([2, 3])
            with col_btn1:
                if st.button("✅ Salvar Lote de Compra", type="primary", use_container_width=True):
                    if fornecedor.strip() == "":
                        st.error("Por favor, preencha o nome do fornecedor!")
                    else:
                        # Adiciona a data e o fornecedor em todos os itens do lote
                        df_lote['Data'] = data_c.strftime("%d/%m/%Y")
                        df_lote['Fornecedor'] = fornecedor
                        
                        # Organiza a ordem das colunas para exibir bonito no histórico
                        df_lote = df_lote[['Data', 'Fornecedor', 'Vinho', 'Qtd', 'Preço Unitário (R$)', 'Custo Total (R$)']]
                        
                        # Junta com o histórico principal de compras
                        st.session_state['compras'] = pd.concat([st.session_state['compras'], df_lote], ignore_index=True)
                        st.session_state['lote_atual'] = [] # Esvazia o lote
                        st.rerun()
            with col_btn2:
                if st.button("🗑️ Limpar / Descartar Lote", use_container_width=False):
                    st.session_state['lote_atual'] = []
                    st.rerun()
        else:
            st.info("O lote está vazio. Use o formulário acima para ir adicionando os vinhos da compra.")

    # Formulário para adicionar nova VENDA
    with tab_venda:
        with st.form("form_venda", clear_on_submit=True):
            st.write("📤 Registrar Venda (Saída Única)")
            vinho_v = st.selectbox("Vinho", df_estoque['Vinho'].unique())
            
            col_v1, col_v2, col_v3 = st.columns(3)
            qtd_v = col_v1.number_input("Qtd (Caixas)", min_value=1, step=1)
            preco_v = col_v2.number_input("Preço de Venda (R$)", min_value=0.0, step=5.0, value=None, placeholder="Ex: 550,00")
            custo_v = col_v3.number_input("Custo da Caixa (R$)", min_value=0.0, step=5.0, value=None, placeholder="Ex: 360,00")
            
            data_v = st.date_input("Data da Venda", datetime.date.today())
            cliente = st.text_input("Cliente")
            
            if st.form_submit_button("Adicionar Venda"):
                if preco_v is None or custo_v is None:
                    st.error("⚠️ Preencha o preço de venda e o custo antes de adicionar!")
                else:
                    nova_venda = pd.DataFrame([{
                        'Vinho': vinho_v, 
                        'Qtd': qtd_v, 
                        'Data': data_v.strftime("%d/%m/%Y"), 
                        'Cliente': cliente,
                        'Preço Venda (R$)': preco_v,
                        'Receita Total (R$)': qtd_v * preco_v,
                        'Custo por Caixa (R$)': custo_v,
                        'Lucro (R$)': (preco_v - custo_v - 90) * qtd_v
                    }])
                    st.session_state['vendas'] = pd.concat([st.session_state['vendas'], nova_venda], ignore_index=True)
                    st.rerun()

    st.divider()
    st.subheader("Histórico de Movimentações")
    
    col_hist_a, col_hist_b = st.columns(2)
    
    with col_hist_a:
        st.write("📥 Compras Registradas")
        st.dataframe(st.session_state['compras'], use_container_width=True)
        
        # UI para excluir um registro de compra
        if not st.session_state['compras'].empty:
            with st.expander("Corrigir / Excluir Compra"):
                opcoes_c = [f"{row['Data']} | {row['Vinho']} ({row['Qtd']} un) - {row['Fornecedor']}" for i, row in st.session_state['compras'].iterrows()]
                idx_c = st.selectbox("Selecione a compra que deseja apagar:", range(len(opcoes_c)), format_func=lambda x: opcoes_c[x], key="sel_c")
                if st.button("❌ Confirmar Exclusão de Compra", key="btn_del_c"):
                    st.session_state['compras'] = st.session_state['compras'].drop(idx_c).reset_index(drop=True)
                    st.rerun()
                    
    with col_hist_b:
        st.write("📤 Vendas Registradas")
        st.dataframe(st.session_state['vendas'], use_container_width=True)
        
        # UI para excluir um registro de venda
        if not st.session_state['vendas'].empty:
            with st.expander("Corrigir / Excluir Venda"):
                opcoes_v = [f"{row['Data']} | {row['Vinho']} ({row['Qtd']} un) - Cliente: {row['Cliente']}" for i, row in st.session_state['vendas'].iterrows()]
                idx_v = st.selectbox("Selecione a venda que deseja apagar:", range(len(opcoes_v)), format_func=lambda x: opcoes_v[x], key="sel_v")
                if st.button("❌ Confirmar Exclusão de Venda", key="btn_del_v"):
                    st.session_state['vendas'] = st.session_state['vendas'].drop(idx_v).reset_index(drop=True)
                    st.rerun()

with tab3:
    st.subheader("Simulador de Margens e Preços")
    st.info("Aqui podemos importar a sua planilha 'loja - Simulação.csv' e criar sliders interativos para prever lucro baseado na margem desejada!")
    
    # Exemplo interativo
    vinho_simulacao = st.selectbox("Selecione um Vinho para simular:", df_saldo['Vinho'].unique())
    custo = st.number_input("Custo por Caixa (R$)", value=None, placeholder="Ex: 100.00", step=5.0)
    preco_venda = st.number_input("Preço de Venda (R$)", value=None, placeholder="Ex: 150.00", step=5.0)
    frete = st.number_input("Custo do Frete (R$)", value=None, placeholder="Ex: 90.00", step=5.0)
    
    if custo is not None and preco_venda is not None and frete is not None:
        if custo > 0:
            margem = ((preco_venda - custo - frete) / custo)*100
        else:
            margem = 0.0
        lucro = preco_venda - custo - frete
        
        st.success(f"**Margem:** {margem:.2f} %")
        st.write(f"**Lucro por caixa:** R$ {lucro:.2f}")

st.divider()
st.caption("Desenvolvido em Python com Streamlit | Sistema de Gestão de Vinhos")
