import streamlit as st
import pandas as pd
import numpy as np

@st.cache
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

uploaded_file = st.file_uploader("Choose a XLS file", type="xls")

if uploaded_file:
    novus_output = pd.read_excel(uploaded_file , skiprows=1)
        # Fecha output novuslis: 0 	2022-06-01 08:11:04
        # fecha input tested : 06/08/2022 07:12:24
    novus_output = novus_output.rename(columns={"Valor": "result" , 'Prestación Estructura': 'nameIndicator',"Unidad": "unitMeasurement", "Fecha":"createdAt","CodFonasa":"code","Orden":"requestId", "Documento":"clientID" , "Paciente": "ClientName" , "CodInterno":"codeInternal" , "Prestacion Orden":"nameExam"})
    # import categories from each examn ( SANGRE, ORINA, etc)

    category_exams = pd.read_csv('category_exams.csv')
    # Drop columns
    novus_output = novus_output.drop(["Programa" , "Edad" , "Sexo"], axis = 1)
    novus_output = novus_output[novus_output.columns.drop(list(novus_output.filter(regex='Unnamed')))]

    # Create empty cols
    novus_output['requestStatus'] = 1
    novus_output['examStatus'] = 1

    #codeIndicator
    loinc_db = pd.read_csv('prestacion_combinaciones_2.csv' , sep='\t',error_bad_lines=False)
    loinc_db = loinc_db.dropna()

    novus_output = pd.merge(left=novus_output, right=loinc_db, how='left', left_on=['nameExam','nameIndicator'], right_on=['Prestacion Orden', 'Prestación Estructura'])
    novus_output = novus_output.drop(['Prestación Estructura' , 'Prestacion Orden'],axis = 1)

    # add category field
    novus_output = pd.merge(left = novus_output, right= category_exams, how='left')
    novus_output['category'][novus_output['nameExam'].str.contains("Orina")] = "ORINA"
    novus_output['category'][novus_output['nameExam'].str.contains("PERFIL LIPIDICO")] = "SANGRE"

    # reportar True en outofrange si analista flageo con *
    novus_output['outOfRange']  = np.where(novus_output['Estado'] == '*', True, False)



    csv = convert_df(novus_output)

    st.download_button(
         label="Download data as CSV",
         data=csv,
         file_name='output.csv',
         mime='text/csv',
     )
