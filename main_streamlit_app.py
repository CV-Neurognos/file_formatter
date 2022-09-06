import streamlit as st
import pandas as pd
import numpy as np


@st.cache
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')


def get_type(cell):
    # Prestaciones que vienen sin rango de referencia , son asignados como other
    if pd.isna(cell):
        return ('other'), None, None
    # 1-. format el contenido de la celda a lower case y convertirlo a un array
    cell_string = cell.lower()
    array_splitted = cell_string.split(' ')

    # 2-. determinar que tipo de rangos tienen:
    # caso hasta:
    if 'hasta' in array_splitted and len(array_splitted) < 4:
        rango_min = 0
        rango_max = array_splitted[1]
        return 'rango_hasta', rango_min, rango_max
    # caso menor a:
    if 'menos' in array_splitted and len(array_splitted) == 3:
        rango_min = 0
        rango_max = array_splitted[2]
        return 'rango_menor', rango_min, rango_max
    # caso min - max:
    if len(array_splitted) == 3 and array_splitted[1] == '-':
        rango_min = array_splitted[0]
        rango_max = array_splitted[2]
        return 'rango', rango_min, rango_max
    if 'negativo' in array_splitted and len(array_splitted) == 1:
        return 'true-false', None, None
    else:
        return 'other', None, None

    # cambiar a confidencial vih


uploaded_file = st.file_uploader("Choose a XLS file", type="xls")

if uploaded_file:
    novus_output = pd.read_excel(uploaded_file, skiprows=1)
    novus_output = novus_output.rename(columns={"Valor": "result", 'Prestación Estructura': 'nameIndicator', "Unidad": "unitMeasurement", "Fecha": "dateExam",
                                                "CodFonasa": "code", "Orden": "requestId", "Documento": "clientId", "Paciente": "clientName", "CodInterno": "codeInternal", "Prestacion Orden": "nameExam"})
    # import categories from each examn ( SANGRE, ORINA, etc)

    category_exams = pd.read_csv('category_exams.csv')
    # Drop columns
    novus_output = novus_output.drop(["Programa", "Edad", "Sexo"], axis=1)
    novus_output = novus_output[novus_output.columns.drop(
        list(novus_output.filter(regex='Unnamed')))]

    # codeIndicator
    loinc_db = pd.read_csv('loinc_db.csv', sep='\t', error_bad_lines=False)
    loinc_db = loinc_db.dropna()

    novus_output = pd.merge(left=novus_output, right=loinc_db, how='left', left_on=[
                            'nameExam', 'nameIndicator'], right_on=['Prestacion Orden', 'Prestación Estructura'])
    novus_output = novus_output.drop(
        ['Prestación Estructura', 'Prestacion Orden'], axis=1)

    # add category field
    novus_output = pd.merge(
        left=novus_output, right=category_exams, how='left')
    novus_output['category'][novus_output['nameExam'].str.contains(
        "Orina")] = "ORINA"
    novus_output['category'][novus_output['nameExam'].str.contains(
        "PERFIL LIPIDICO")] = "SANGRE"
    novus_output['category'][novus_output['nameExam'].str.contains(
        "PERFIL BIOQUIMICO")] = "SANGRE"
    novus_output['category'][novus_output['nameExam'].str.contains(
        "PERFIL HEPÁTICO")] = "SANGRE"

    # reportar True en outofrange si analista flageo con *
    novus_output['outOfRange'] = np.where(
        novus_output['Estado'] == '*', 'true', 'false')

    # asignar tipo de rango y valores inferiores y superiores.
    novus_output['categoryIndicator'], novus_output['referenceInf'], novus_output['referenceSup'] = zip(
        *novus_output['Rango Ref'].apply(get_type))

    # cambiar nombre a vih
    novus_output.loc[novus_output.nameExam ==
                     'HIV.ISP', 'categoryIndicator'] = 'confidencial'
    novus_output.loc[novus_output.nameExam ==
                     'HIV', 'categoryIndicator'] = 'confidencial'

    # reference verification Orina
    novus_output['referenceVerification(ORINA/DEFINIR)'] = np.nan
    novus_output['descriptionIndicator'] = np.nan
    novus_output['examStatus'] = 1

    # llenar reultados otherResults. # si la categoria es other, agregar el rango de referencia
    novus_output['otherResults'] = np.nan
    novus_output['otherResults'] = np.where(
        novus_output['categoryIndicator'] == 'other', novus_output['Rango Ref'], np.nan)

    # llenar resultados requestStatus. # si el resultado esta vacio, cambair requestStatus a Incomplete,
    novus_output['requestStatus'] = np.where(
        novus_output['result'].isnull(), 'Pending', 'Complete')

    # drop columnas sobrantes
    # referenceVerification(ORINA/DEFINIR)

    #novus_output = novus_output.drop(['Estado' , 'Rango Ref'],axis = 1)

    csv = convert_df(novus_output)

    st.download_button(
        label="Download data as CSV",
        data=csv,
        file_name='output.csv',
        mime='text/csv',
    )
