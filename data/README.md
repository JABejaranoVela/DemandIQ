# Datos locales

Solo se versiona este README. Esta carpeta aloja:

- raw/: originales proporcionados por el usuario.
- archive/: copias por SHA-256 al usar la CLI local.

En esta fase se procesan sales_train_evaluation.csv y calendar.csv.
sell_prices.csv queda pendiente. No se incluyen archivos ni muestras reales M5.
Las condiciones de redistribución deben verificarse; no guardar credenciales de Kaggle aquí.

Docker monta raw/ en lectura y usa un volumen para el archivo de originales.
El archivo conserva originales completos, aunque se transforme un subconjunto.
