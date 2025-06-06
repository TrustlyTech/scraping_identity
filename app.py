from flask import Flask, jsonify
import os
import requests
import json
import base64
import psycopg2
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

app = Flask(__name__)

# Azure Face API
AZURE_FACE_API_KEY = 'c5eeb55cfbc442f0883e8b0a13a36480'
AZURE_FACE_ENDPOINT = 'https://detection1234.cognitiveservices.azure.com/'
LARGE_PERSON_GROUP_ID = 'requisitoriados-group02'

# PostgreSQL config
DB_URL = "postgresql://requisitoriados_user:x0xLGMH3N71ZfUG9UX7rcBiujKiELzKY@dpg-d114ho2li9vc738covqg-a.oregon-postgres.render.com/requisitoriados"

def connect_db():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_db():
    conn = connect_db()
    cur = conn.cursor()
    
    # Borra la tabla si existe
    cur.execute("DROP TABLE IF EXISTS requisitoriados;")
    
    # Crea la tabla nuevamente
    cur.execute("""
        CREATE TABLE requisitoriados (
            id SERIAL PRIMARY KEY,
            nombre TEXT,
            recompensa TEXT,
            imagen TEXT
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


def insert_person_db(nombre, recompensa, imagen):
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO requisitoriados (nombre, recompensa, imagen)
            VALUES (%s, %s, %s);
        """, (nombre, recompensa, imagen))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error al insertar en la base de datos: {e}")

def create_large_person_group():
    base_url = f"{AZURE_FACE_ENDPOINT}/face/v1.0/largepersongroups/{LARGE_PERSON_GROUP_ID}"
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_FACE_API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        "name": "Requisitoriados",
        "userData": "Grupo de personas buscadas",
        "recognitionModel": "recognition_04"
    }
    response = requests.put(base_url, headers=headers, json=data)
    if response.status_code == 200:
        print("Grupo creado con éxito.")
    elif response.status_code == 409:
        print("Grupo ya existe. Eliminando y recreando...")
        delete_response = requests.delete(base_url, headers=headers)
        if delete_response.status_code == 200:
            print("Grupo eliminado.")
            recreate_response = requests.put(base_url, headers=headers, json=data)
            if recreate_response.status_code == 200:
                print("Grupo recreado con éxito.")
            else:
                print(f"Error al recrear el grupo: {recreate_response.status_code}, {recreate_response.text}")
        else:
            print(f"Error al eliminar el grupo: {delete_response.status_code}, {delete_response.text}")
    else:
        print(f"Error creando el grupo: {response.status_code}, {response.text}")

def create_person_in_group(person_name, user_data):
    url = f"{AZURE_FACE_ENDPOINT}/face/v1.0/largepersongroups/{LARGE_PERSON_GROUP_ID}/persons"
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_FACE_API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        "name": person_name,
        "userData": user_data
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["personId"]
    else:
        print(f"Error creando persona: {response.status_code}, {response.text}")
        return None

def add_face_to_person(person_id, person_name, image_path):
    url = f"{AZURE_FACE_ENDPOINT}/face/v1.0/largepersongroups/{LARGE_PERSON_GROUP_ID}/persons/{person_id}/persistedfaces"
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_FACE_API_KEY,
        'Content-Type': 'application/octet-stream'
    }
    with open(image_path, 'rb') as image:
        response = requests.post(url, headers=headers, data=image)
    if response.status_code == 200:
        print(f"Imagen cargada para: {person_name}")
    else:
        print(f"Error al agregar rostro para {person_name}: {response.status_code}, {response.text}")

def train_person_group():
    url = f"{AZURE_FACE_ENDPOINT}/face/v1.0/largepersongroups/{LARGE_PERSON_GROUP_ID}/train"
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_FACE_API_KEY
    }
    response = requests.post(url, headers=headers)
    if response.status_code == 202:
        print("Entrenamiento iniciado correctamente.")
    else:
        print(f"Error al iniciar entrenamiento: {response.status_code}, {response.text}")

def save_base64_image(base64_string, filename):
    image_data = base64_string.split(",")[1]
    with open(filename, "wb") as f:
        f.write(base64.b64decode(image_data))

def extract_images():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    if not os.path.exists('imagenes'):
        os.makedirs('imagenes')

    url = 'https://www.recompensas.pe/requisitoriados'
    driver.get(url)

    try:
        btn = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.CLASS_NAME, 'btn-danger')))
        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", btn)
    except Exception as e:
        print(f"Error al hacer clic en el botón de ingreso: {e}")
        driver.quit()
        return

    while True:
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, 'card')))
        items = driver.find_elements(By.CLASS_NAME, 'card')

        for index, item in enumerate(items):
            try:
                name = item.find_element(By.CLASS_NAME, 'card-title').text
                reward = item.find_element(By.CLASS_NAME, 'card-text').text
                image_element = item.find_element(By.TAG_NAME, 'img')
                image_url = image_element.get_attribute('src')

                print(f"Cargando: Nombre: {name} | Recompensa: {reward}")

                safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip()
                image_filename = f'imagenes/{safe_name}_{index}.png'

                if image_url.startswith("data:image"):
                    save_base64_image(image_url, image_filename)
                    image_url = image_filename

                # Azure
                person_id = create_person_in_group(name, reward)
                if person_id:
                    add_face_to_person(person_id, name, image_url)

                # DB
                insert_person_db(name, reward, image_url)

            except Exception as e:
                print(f'Error al procesar un item: {e}')

        try:
            next_page_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'ul.pagination > li:nth-last-child(2) > a'))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", next_page_button)
            time.sleep(1)
            next_page_button.click()
            time.sleep(2)
        except Exception:
            break

    driver.quit()

@app.route('/extract_and_upload', methods=['GET'])
def extract_and_upload():
    init_db()
    create_large_person_group()
    extract_images()
    train_person_group()
    return jsonify({"message": "Extracción, carga y entrenamiento completados con éxito"}), 200

@app.route('/')
def home():
    return jsonify({"status": "API activa. Usa /extract_and_upload para comenzar."})

if __name__ == '__main__':
    app.run(debug=True)
