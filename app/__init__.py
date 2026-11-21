"""Aplicativo de escritorio "Registro de Licitaciones".

Paquetes y módulos:
    config      lectura y escritura de la configuración de conexión
    db          acceso a PostgreSQL (llamadas a procedimientos y consultas)
    errores     traducción de errores de PostgreSQL a mensajes para el usuario
    catalogo    descripción de las 14 tablas que el aplicativo administra
    reportes    descripción de los 13 reportes (vistas vw_rep*)
    ui          interfaz gráfica en Tkinter (ventanas y controles)
"""

NOMBRE = "Registro de Licitaciones"
VERSION = "1.1.0"
