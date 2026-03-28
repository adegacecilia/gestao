import streamlit as st
import pandas as pd
import io
import datetime # Para pegar a data atual automaticamente nos formulários

# Configuração da página do Streamlit
st.set_page_config(page_title="Gestão de Vinhos", page_icon="🍷", layout="wide")

st.title("🍷 Sistema de Gestão de Vinhos")
st.markdown("Adega Cecília")

# --- PERSONALIZAÇÃO VISUAL (CSS) ---
st.markdown("""
    <style>
    /* Remove a borda e o brilho vermelho ao focar/clicar nas caixas de seleção (selectbox) e inputs */
    div[data-baseweb="select"] > div:focus-within {
        box-shadow: none !important;
        border-color: #cccccc !important;
    }
    div[data-baseweb="input"] > div:focus-within {
        box-shadow: none !important;
        border-color: #cccccc !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 0. INICIALIZAÇÃO DA SESSÃO (MEMÓRIA DO APP) ---
if 'compras' not in st.session_state:
    st.session_state['compras'] = pd.DataFrame(columns=['Data', 'Fornecedor', 'Vinho', 'Qtd', 'Preço por Caixa (R$)', 'Custo Total (R$)', 'Status'])
else:
    # Garante que as compras anteriores à atualização tenham o campo Status
    if 'Status' not in st.session_state['compras'].columns:
        st.session_state['compras']['Status'] = 'Estoque'

if 'vendas' not in st.session_state:
    st.session_state['vendas'] = pd.DataFrame(columns=['Vinho', 'Qtd', 'Data', 'Cliente', 'Preço Venda (R$)', 'Receita Total (R$)', 'Custo por Caixa (R$)', 'Lucro (R$)'])

if 'lote_atual' not in st.session_state:
    st.session_state['lote_atual'] = []

# Memória para rastrear os vinhos do CSV (Estoque Inicial) que chegaram
if 'recebidos_iniciais' not in st.session_state:
    st.session_state['recebidos_iniciais'] = []

# --- 1. CARREGAMENTO DOS DADOS ---
@st.cache_data
def carregar_estoque_inicial():
    try:
        df_estoque = pd.read_csv('loja - Estoque.csv')
    except FileNotFoundError:
        csv_estoque = """Vinho,Estoque Inicial,Status\nChandon Brut,2,M&A\nEl Enemigo Chardonnay,3,M&A\nNicola Bonarda,2,Transporte"""
        df_estoque = pd.read_csv(io.StringIO(csv_estoque))
    return df_estoque

df_estoque_raw = carregar_estoque_inicial()

# Padroniza o status do CSV inicial (Verifica se já foi marcado como recebido no App)
df_estoque = df_estoque_raw.copy()
df_estoque['Status_Norm'] = df_estoque.apply(
    lambda row: 'Estoque' if row.name in st.session_state['recebidos_iniciais'] 
                else ('Em transporte' if str(row['Status']).strip().lower() in ['transporte', 'em transporte'] else 'Estoque'), 
    axis=1
)

@st.cache_data
def carregar_precos():
    try:
        df_precos = pd.read_csv('loja - Precos.csv')
    except FileNotFoundError:
        try:
            df_precos = pd.read_csv('loja - Simulação.csv')
        except FileNotFoundError:
            csv_precos = """Vinho,Custo,Venda\nAlma Negra,360,550\nAlamos Malbec,90,205\nMalbec Argentino,940,1280"""
            df_precos = pd.read_csv(io.StringIO(csv_precos))
    
    def limpar_moeda(valor):
        if isinstance(valor, str):
            valor = valor.replace('R$', '').replace('.', '').replace(',', '.').strip()
        return pd.to_numeric(valor, errors='coerce')
        
    if 'Custo' in df_precos.columns:
        df_precos['Custo'] = df_precos['Custo'].apply(limpar_moeda)
    if 'Venda' in df_precos.columns:
        df_precos['Venda'] = df_precos['Venda'].apply(limpar_moeda)
        
    return df_precos

df_precos = carregar_precos()
df_compras = st.session_state['compras']
df_vendas = st.session_state['vendas']

# --- 2. PROCESSAMENTO E LÓGICA DE NEGÓCIO ---

# 2.1 Agrupar Estoque Inicial
estoque_fisico_ini = df_estoque[df_estoque['Status_Norm'] == 'Estoque'].groupby('Vinho')['Estoque Inicial'].sum().reset_index().rename(columns={'Estoque Inicial': 'Físico Inicial'})
estoque_transporte_ini = df_estoque[df_estoque['Status_Norm'] == 'Em transporte'].groupby('Vinho')['Estoque Inicial'].sum().reset_index().rename(columns={'Estoque Inicial': 'Transporte Inicial'})

# 2.2 Agrupar Compras (Separando o que é físico do que é transporte)
if not df_compras.empty:
    compras_fisico = df_compras[df_compras['Status'] == 'Estoque'].groupby('Vinho')['Qtd'].sum().reset_index().rename(columns={'Qtd': 'Compras Físico'})
    compras_transporte = df_compras[df_compras['Status'] == 'Em transporte'].groupby('Vinho')['Qtd'].sum().reset_index().rename(columns={'Qtd': 'Compras Transporte'})
else:
    compras_fisico = pd.DataFrame(columns=['Vinho', 'Compras Físico'])
    compras_transporte = pd.DataFrame(columns=['Vinho', 'Compras Transporte'])

# 2.3 Agrupar Vendas
if not df_vendas.empty:
    vendas_agrupadas = df_vendas.groupby('Vinho')['Qtd'].sum().reset_index().rename(columns={'Qtd': 'Total Vendido'})
else:
    vendas_agrupadas = pd.DataFrame(columns=['Vinho', 'Total Vendido'])

# 2.4 Juntar (Merge) as tabelas para calcular os Saldos
todos_vinhos = pd.concat([df_estoque['Vinho'], df_compras['Vinho'] if not df_compras.empty else pd.Series(), df_vendas['Vinho'] if not df_vendas.empty else pd.Series()]).dropna().unique()
df_saldo = pd.DataFrame({'Vinho': todos_vinhos})

df_saldo = pd.merge(df_saldo, estoque_fisico_ini, on='Vinho', how='left').fillna(0)
df_saldo = pd.merge(df_saldo, estoque_transporte_ini, on='Vinho', how='left').fillna(0)
df_saldo = pd.merge(df_saldo, compras_fisico, on='Vinho', how='left').fillna(0)
df_saldo = pd.merge(df_saldo, compras_transporte, on='Vinho', how='left').fillna(0)
df_saldo = pd.merge(df_saldo, vendas_agrupadas, on='Vinho', how='left').fillna(0)

# 2.5 Cálculos Finais de Colunas
df_saldo['Em Transporte'] = df_saldo['Transporte Inicial'] + df_saldo['Compras Transporte']
df_saldo['Estoque Físico'] = df_saldo['Físico Inicial'] + df_saldo['Compras Físico'] - df_saldo['Total Vendido']
df_saldo['Estoque Total'] = df_saldo['Estoque Físico'] + df_saldo['Em Transporte']

# --- 3. INTERFACE VISUAL (DASHBOARD) ---

# Criando abas para organização
tab1, tab2, tab3 = st.tabs(["📊 Visão Geral", "🛒 Movimentações", "📈 Simulações"])

with tab1:
    st.subheader("Resumo do Estoque Atual")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Rótulos", len(df_saldo))
    col2.metric("📦 Estoque Físico (cx)", f"{(df_saldo['Estoque Físico'].sum()):.0f}")
    col3.metric("🚚 Em Transporte (cx)", f"{(df_saldo['Em Transporte'].sum()):.0f}")
    col4.metric("Total Vendido (cx)", f"{(df_saldo['Total Vendido'].sum()):.0f}")
    
    st.divider()
    st.subheader("📈 Desempenho de Vendas & Lucro")
    
    df_v = st.session_state['vendas'].copy()
    if not df_v.empty:
        df_v['Data_dt'] = pd.to_datetime(df_v['Data'], format="%d/%m/%Y", errors='coerce')
        
        st.markdown("##### 📅 Filtrar Período")
        col_cal1, col_cal2 = st.columns(2)
        hoje = datetime.date.today()
        primeiro_dia_mes = hoje.replace(day=1)
        
        start_date = col_cal1.date_input("Data Inicial", primeiro_dia_mes, format="DD/MM/YYYY")
        end_date = col_cal2.date_input("Data Final", hoje, format="DD/MM/YYYY")
        
        mask = (df_v['Data_dt'].dt.date >= start_date) & (df_v['Data_dt'].dt.date <= end_date)
        vendas_periodo = df_v[mask]
        
        caixas = vendas_periodo['Qtd'].sum() if not vendas_periodo.empty else 0
        lucro_total = vendas_periodo['Lucro (R$)'].sum() if not vendas_periodo.empty else 0
        lucro_por_caixa = (lucro_total / caixas) if caixas > 0 else 0
        
        st.markdown(f"**Resultados de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}:**")
        col_d1, col_d2, col_d3 = st.columns(3)
        col_d1.metric("📦 Caixas Vendidas", f"{caixas}")
        col_d2.metric("💰 Lucro Total", f"R$ {lucro_total:,.2f}")
        col_d3.metric("📊 Lucro Médio por Caixa", f"R$ {lucro_por_caixa:,.2f}")
    else:
        st.info("Registre algumas vendas na aba 'Movimentações' para ver os indicadores de desempenho de caixas e lucro!")
        
    st.divider()
    
    # Exibir tabela de saldo limpa com foco no status
    df_exibicao = df_saldo[['Vinho', 'Estoque Físico', 'Em Transporte', 'Estoque Total', 'Total Vendido']]
    st.dataframe(
        df_exibicao.style.format({
            'Estoque Físico': '{:.0f}',
            'Em Transporte': '{:.0f}',
            'Estoque Total': '{:.0f}',
            'Total Vendido': '{:.0f}'
        }),
        use_container_width=True
    )
    
    # Gráfico simples de estoque atual por Vinho (Empilhado)
    st.subheader("Estoque por Rótulo (Caixas)")
    st.bar_chart(df_saldo.set_index('Vinho')[['Estoque Físico', 'Em Transporte']])

with tab2:
    st.subheader("Gerenciar Estoque e Movimentações")
    
    tab_compra, tab_venda, tab_entregas = st.tabs(["🛒 Compras (Entrada em Lote)", "📤 Vendas (Saídas)", "🚚 Entregas (Recebimento)"])
    
    with tab_compra:
        st.markdown("### 📥 Registrar Novo Lote")
        
        col_info1, col_info2 = st.columns(2)
        data_c = col_info1.date_input("Data da Compra", datetime.date.today(), format="DD/MM/YYYY")
        fornecedor = col_info2.text_input("Fornecedor", placeholder="Ex: Márcia")
        
        st.markdown("#### 1. Adicionar Vinhos ao Lote")
        with st.form("form_item_lote", clear_on_submit=True):
            col_a, col_b, col_c = st.columns([2, 1, 1])
            
            lista_vinhos_estoque = sorted(df_estoque['Vinho'].unique())
            vinho_c = col_a.selectbox("Vinho", lista_vinhos_estoque)
            
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
        
        if len(st.session_state['lote_atual']) > 0:
            st.write("📋 **Itens no Lote Atual:**")
            for i, item in enumerate(st.session_state['lote_atual']):
                c1, c2, c3 = st.columns([4, 2, 1])
                c1.write(f"🍷 **{item['Vinho']}** ({item['Qtd']} cx a R$ {item['Preço por Caixa (R$)']:.2f})")
                c2.write(f"Subtotal: R$ {item['Custo Total (R$)']:.2f}")
                if c3.button("❌", key=f"del_lote_{i}", help="Excluir este vinho do lote"):
                    st.session_state['lote_atual'].pop(i)
                    st.rerun()
            
            df_lote = pd.DataFrame(st.session_state['lote_atual'])
            
            total_qtd = df_lote['Qtd'].sum()
            total_custo = df_lote['Custo Total (R$)'].sum()
            total_custo_frete = total_qtd * 90
            
            col_tot1, col_tot2 = st.columns(2)
            col_tot1.metric("Total de Caixas no Lote", total_qtd)
            col_tot2.metric("Valor Total do Lote + Frete", f"R\$ {total_custo:,.2f}" " + " f"R\$ {total_custo_frete:,.2f}")
            
            st.markdown("#### 2. Confirmar Lote")
            
            # Aqui definimos se a compra está em transporte ou se já chegou
            status_lote = st.radio("Situação da Compra:", ["🚚 Em transporte", "📦 Já chegou (No Estoque)"], horizontal=True)
            status_final = 'Em transporte' if "Em transporte" in status_lote else 'Estoque'
            
            col_btn1, col_btn2 = st.columns([2, 3])
            with col_btn1:
                if st.button("✅ Salvar Lote de Compra", type="primary", use_container_width=True):
                    if fornecedor.strip() == "":
                        st.error("Por favor, preencha o nome do fornecedor!")
                    else:
                        df_lote['Data'] = data_c.strftime("%d/%m/%Y")
                        df_lote['Fornecedor'] = fornecedor
                        df_lote['Status'] = status_final
                        
                        df_lote = df_lote[['Data', 'Fornecedor', 'Vinho', 'Qtd', 'Preço por Caixa (R$)', 'Custo Total (R$)', 'Status']]
                        
                        st.session_state['compras'] = pd.concat([st.session_state['compras'], df_lote], ignore_index=True)
                        st.session_state['lote_atual'] = []
                        st.rerun()
            with col_btn2:
                if st.button("🗑️ Limpar / Descartar Lote", use_container_width=False):
                    st.session_state['lote_atual'] = []
                    st.rerun()
        else:
            st.info("O lote está vazio. Use o formulário acima para ir adicionando os vinhos da compra.")

    with tab_venda:
        st.write("📤 Registrar Venda (Saída Única)")
        
        lista_vinhos_estoque = sorted(df_estoque['Vinho'].unique())
        vinho_v = st.selectbox("Vinho", lista_vinhos_estoque)
        
        custo_sugerido = None
        preco_v_sugerido = None
        if vinho_v in df_precos['Vinho'].values:
            linha = df_precos[df_precos['Vinho'] == vinho_v].iloc[0]
            if 'Custo' in df_precos.columns and pd.notna(linha['Custo']):
                custo_sugerido = float(linha['Custo'])
            if 'Venda' in df_precos.columns and pd.notna(linha['Venda']):
                preco_v_sugerido = float(linha['Venda'])

        with st.form("form_venda", clear_on_submit=True):
            col_v1, col_v2, col_v3 = st.columns(3)
            qtd_v = col_v1.number_input("Qtd (Caixas)", min_value=1, step=1)
            preco_v = col_v2.number_input("Preço de Venda (R$)", min_value=0.0, step=5.0, value=preco_v_sugerido, placeholder="Ex: 550,00")
            custo_v = col_v3.number_input("Custo da Caixa (R$)", min_value=0.0, step=5.0, value=custo_sugerido, placeholder="Ex: 360,00")
            
            data_v = st.date_input("Data da Venda", datetime.date.today(), format="DD/MM/YYYY")
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

    with tab_entregas:
        st.write("Marque as compras e mercadorias que acabaram de chegar fisicamente na adega.")
        
        pendentes_iniciais = df_estoque[df_estoque['Status_Norm'] == 'Em transporte']
        pendentes_compras = st.session_state['compras'][st.session_state['compras']['Status'] == 'Em transporte']
        
        if not pendentes_iniciais.empty or not pendentes_compras.empty:
            
            if not pendentes_iniciais.empty:
                st.markdown("#### 📦 Pendências do Estoque Inicial")
                for idx, row in pendentes_iniciais.iterrows():
                    c1, c2 = st.columns([5, 1])
                    c1.write(f"🍷 **{row['Vinho']}** - {row['Estoque Inicial']} cx pendentes")
                    if c2.button("✅ Receber", key=f"rec_ini_{idx}", help="Transferir para o Estoque Físico"):
                        st.session_state['recebidos_iniciais'].append(idx)
                        st.rerun()
                        
            if not pendentes_compras.empty:
                st.markdown("#### 📦 Pendências de Novas Compras")
                for idx, row in pendentes_compras.iterrows():
                    c1, c2 = st.columns([5, 1])
                    c1.write(f"📅 {row['Data']} | 🍷 **{row['Vinho']}** - {row['Qtd']} cx (Fornecedor: {row['Fornecedor']})")
                    if c2.button("✅ Receber", key=f"rec_comp_{idx}", help="Transferir para o Estoque Físico"):
                        st.session_state['compras'].at[idx, 'Status'] = 'Estoque'
                        st.rerun()
        else:
            st.success("🎉 Tudo em dia! Nenhuma entrega pendente de transportadora no momento.")

    st.divider()
    st.subheader("Histórico de Movimentações")
    
    col_hist_a, col_hist_b = st.columns(2)
    with col_hist_a:
        st.write("📥 Compras Registradas")
        st.dataframe(st.session_state['compras'], use_container_width=True)
        
        if not st.session_state['compras'].empty:
            with st.expander("Corrigir / Excluir Compra"):
                opcoes_c = [f"{row['Data']} | {row['Vinho']} ({row['Qtd']} cx) - {row['Fornecedor']}" for i, row in st.session_state['compras'].iterrows()]
                idx_c = st.selectbox("Selecione a compra que deseja apagar:", range(len(opcoes_c)), format_func=lambda x: opcoes_c[x], key="sel_c")
                if st.button("❌ Confirmar Exclusão de Compra", key="btn_del_c"):
                    st.session_state['compras'] = st.session_state['compras'].drop(idx_c).reset_index(drop=True)
                    st.rerun()
                    
    with col_hist_b:
        st.write("📤 Vendas Registradas")
        st.dataframe(st.session_state['vendas'], use_container_width=True)
        
        if not st.session_state['vendas'].empty:
            with st.expander("Corrigir / Excluir Venda"):
                opcoes_v = [f"{row['Data']} | {row['Vinho']} ({row['Qtd']} cx) - Cliente: {row['Cliente']}" for i, row in st.session_state['vendas'].iterrows()]
                idx_v = st.selectbox("Selecione a venda que deseja apagar:", range(len(opcoes_v)), format_func=lambda x: opcoes_v[x], key="sel_v")
                if st.button("❌ Confirmar Exclusão de Venda", key="btn_del_v"):
                    st.session_state['vendas'] = st.session_state['vendas'].drop(idx_v).reset_index(drop=True)
                    st.rerun()

with tab3:
    st.subheader("Simulador de Margens e Preços")
    st.info("Aqui podemos importar a sua planilha 'loja - Simulação.csv' e criar sliders interativos para prever lucro baseado na margem desejada!")
    
    lista_vinhos_simulacao = sorted(df_saldo['Vinho'].unique())
    vinho_simulacao = st.selectbox("Selecione um Vinho para simular:", lista_vinhos_simulacao)
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
