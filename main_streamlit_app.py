#################################################################################
#####################       LIBRERIAS y FUNCIONES    ############################
#################################################################################

import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from pyxlsb import open_workbook as open_xlsb
#import time


@st.cache
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

@st.cache
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    workbook = writer.book
    worksheet = writer.sheets['Sheet1']
    format1 = workbook.add_format({'num_format': '0.00'})
    worksheet.set_column('A:A', None, format1)
    writer.save()
    processed_data = output.getvalue()
    return processed_data


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


DICT_COLNAMES = {"Valor": "result", 'Prestación Estructura': 'nameIndicator', "Unidad": "unitMeasurement", "Fecha": "dateExam", "CodFonasa": "code",
                 "Orden": "requestId", "Documento": "clientId", "Paciente": "clientName", "CodInterno": "codeInternal", "Prestacion Orden": "nameExam"}

DICT_COLNAMES_BM = {'Fecha solicitud':'dateExam', 'Documento':'clientId','Prestacion':'nameExam', 'Resultado':'result', 'Orden':'requestId'}
BORRAR = ['Toma muestra','Fecha nacimiento','Validación','Procedencia','TipoDoc','Nombre', 'ApellidoPaterno','ApellidoMaterno','Edad','Sexo','Comuna','Dirección','Telefono','Email']
#################################################################################
#####################            STREAMLIT           ############################
#################################################################################
st.header('NOVUSLIS CORE')
uploaded_file = st.file_uploader("Choose a XLS file", type="xls")

if uploaded_file:
    # import novuslis output

    novus_output = pd.read_excel(uploaded_file, skiprows=1 , parse_dates=['Fecha'] , dtype={'CodInterno': object,'CodFonasa': object,'Documento': object})


    # cambiar de nombre columnas - usando dict_colnames
    novus_output = novus_output.rename(columns=DICT_COLNAMES)

    # formatear fecha '2022-08-01 08:46:05' a '2022-08-01'
    novus_output['dateExam'] = novus_output['dateExam'].dt.date

    # Drop columns
    novus_output = novus_output.drop(["Programa", "Edad", "Sexo"], axis=1)
    novus_output = novus_output[novus_output.columns.drop(
        list(novus_output.filter(regex='Unnamed')))]

    # Agregar codigos LOINC: codeIndicator
    loinc_db = pd.read_csv('loinc_db.csv', sep='\t', error_bad_lines=False)
    loinc_db = loinc_db.dropna()

    novus_output = pd.merge(left=novus_output, right=loinc_db, how='left', left_on=[
                            'nameExam', 'nameIndicator'], right_on=['Prestacion Orden', 'Prestación Estructura'])
    novus_output = novus_output.drop(
        ['Prestación Estructura', 'Prestacion Orden'], axis=1)

    # import categories ( SANGRE, ORINA, etc)
    category_exams = pd.read_csv('category_exams.csv')
    novus_output = pd.merge(
        left=novus_output, right=category_exams, how='left')

    # Agregar SANGRE/ORINA a paneles conocidos
    novus_output['category'][novus_output['nameExam'].str.contains(
        "Orina")] = "ORINA"

    novus_output['category'][novus_output['nameExam'].str.contains(
        'PERFIL HEPÁTICO|PERFIL BIOQUIMICO|PERFIL LIPIDICO"', regex=True)] = "SANGRE"

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

    # examStatus
    novus_output['examStatus'] = np.where(
        novus_output['result'].isnull(), 'PENDING', 'COMPLETE')

    # llenar reultados otherResults. # si la categoria es other, agregar el rango de referencia
    novus_output['otherResults'] = np.nan
    novus_output['otherResults'] = np.where(
        novus_output['categoryIndicator'] == 'other', novus_output['Rango Ref'], np.nan)

    # llenar resultados requestStatus. # si el resultado esta vacio, cambair requestStatus a Incomplete,
    novus_output['requestStatus'] = novus_output['examStatus']

    # add missing values to code column
    #start = time.time()
    splitted_code_internal = novus_output['codeInternal'].astype("string").apply(lambda x: x.split('-')[0])
    novus_output['code'] = np.where(novus_output['code'].astype("string") == '-', splitted_code_internal, novus_output['code'])
    #end = time.time()
    #time_ex = (end-start) * 10**3
    #st.write(time_ex)
    # novus_output['code'] = novus_output['code'].apply(lambda x: x.str.split('-', 1)[0] if x == '' else x)
    #


    # drop columnas sobrantes
    novus_output = novus_output.drop(['Estado', 'Rango Ref'], axis=1)

    #csv = convert_df(novus_output)
    df_xlsx = to_excel(novus_output)


    st.download_button(
        label="Download data as .xlsx",
        data=df_xlsx,
        file_name='output.xlsx'
    )


st.header('NOVUSLIS BM')
uploaded_file_bm = st.file_uploader("Archivo XLS novuslis BM", type="xls")
if uploaded_file_bm:
    # import novuslis output
    df_novus_bm = pd.read_excel(uploaded_file_bm, parse_dates=['Fecha solicitud'])
    df_novus_bm = df_novus_bm.fillna('')

    # cambiar de nombre columnas - usando dict_colnames_2
    df_novus_bm = df_novus_bm.rename(columns=DICT_COLNAMES_BM)

    # formatear fecha '2022-08-01 08:46:05' a '2022-08-01'
    df_novus_bm['dateExam'] = df_novus_bm['dateExam'].dt.date

    # concatenar columna de nombres
    df_novus_bm['clientName'] = df_novus_bm['Nombre'] + ' ' + df_novus_bm['ApellidoPaterno'] + ' ' + df_novus_bm['ApellidoMaterno']

    #drop columnas innecesarias
    df_novus_bm = df_novus_bm.drop(BORRAR, axis = 1)

    # Agregar columnas para completar formateado

    df_novus_bm['unitMeasurement'] = np.nan
    df_novus_bm['codeInternal'] = np.nan
    df_novus_bm['code'] = np.nan
    df_novus_bm['category'] = np.nan
    df_novus_bm['nameIndicator'] = np.nan
    df_novus_bm['referenceInf'] = np.nan
    df_novus_bm['referenceSup'] = np.nan
    df_novus_bm['otherResults'] = np.nan

    # asignar nameIndicators
    df_novus_bm['nameIndicator'][df_novus_bm['nameExam'].str.contains('ANTIGENO')] = 'CORONAVIRUS ANTI-SARS-CoV-2, IgG'
    df_novus_bm['nameIndicator'][df_novus_bm['nameExam'].str.contains('PCR SARS-CoV-2|Test de saliva Covid-19')] = 'SARS-CoV-2 (COVID-19) RNA'

    # Agregar codigos LOINC: codeIndicator
    loinc_db = pd.read_csv('loinc_db.csv', sep='\t', error_bad_lines=False)
    loinc_db = loinc_db.dropna()
    df_novus_bm = pd.merge(left=df_novus_bm, right=loinc_db, how='left', left_on=['nameExam', 'nameIndicator'], right_on=['Prestacion Orden', 'Prestación Estructura'])
    df_novus_bm = df_novus_bm.drop(['Prestación Estructura', 'Prestacion Orden'], axis=1)


    # agregar columnas outOfRange y categoryIndicator
    df_novus_bm['categoryIndicator'] = 'true-false'
    df_novus_bm['outOfRange'] = np.where(df_novus_bm['result'].str.lower() == 'negativo', 'false', 'true')

    # examStatus
    df_novus_bm['examStatus'] = np.where(df_novus_bm['result'].isnull(), 'PENDING', 'COMPLETE')

    #df_novus_bm['otherResults'] = np.where(df_novus_bm['categoryIndicator'] == 'other', df_novus_bm['Rango Ref'], np.nan)

    # llenar resultados requestStatus. # si el resultado esta vacio, cambair requestStatus a Incomplete,
    df_novus_bm['requestStatus'] = df_novus_bm['examStatus']

    # asignar code y codeInternal
    df_novus_bm['code'][df_novus_bm['codeIndicator'].str.contains('95209-3')] = '0006060'
    df_novus_bm['code'][df_novus_bm['codeIndicator'].str.contains('94309-2')] = '0306082'
    df_novus_bm['codeInternal'] = df_novus_bm['code']

    #csv = convert_df(novus_output)
    df_xlsx = to_excel(df_novus_bm)

    st.download_button(
        label="Download data as .xlsx",
        data=df_xlsx,
        file_name='output.xlsx'
    )
