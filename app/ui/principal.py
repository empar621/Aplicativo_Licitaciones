"""Ventana principal: menú lateral, área de trabajo y barra de estado."""

import tkinter as tk
from tkinter import messagebox, ttk

from .. import NOMBRE, VERSION
from ..catalogo import MENU, POR_TABLA
from . import estilo
from .inicio import PanelInicio
from .menu_lateral import MenuLateral
from .pantalla_entidad import PantallaEntidad
from .pantalla_reportes import PantallaReportes


class VentanaPrincipal:
    """Arma la ventana raíz una vez conectada la base de datos."""

    def __init__(self, raiz: tk.Tk, db, maximizada: bool = True):
        self.raiz = raiz
        self.db = db
        self.pantallas = {}   # clave del menú -> pantalla ya construida
        self.actual = None

        raiz.title(NOMBRE)
        raiz.geometry(f"{estilo.px(raiz, 1280)}x{estilo.px(raiz, 760)}")
        raiz.minsize(estilo.px(raiz, 1040), estilo.px(raiz, 640))
        if maximizada:
            try:
                raiz.state("zoomed")    # las tablas aprovechan todo el ancho de la pantalla
            except tk.TclError:
                pass                    # gestor de ventanas sin estado "zoomed"
        raiz.configure(background=estilo.FONDO)
        raiz.protocol("WM_DELETE_WINDOW", self.salir)
        self._barra_de_menus()

        self.estado = ttk.Label(raiz, style="Estado.TLabel", anchor="w")
        self.estado.pack(side="bottom", fill="x")

        cuerpo = ttk.Frame(raiz)
        cuerpo.pack(fill="both", expand=True)
        self.menu = MenuLateral(cuerpo, self._secciones(), self._mostrar)
        self.menu.pack(side="left", fill="y")
        self.contenedor = ttk.Frame(cuerpo)
        self.contenedor.pack(side="left", fill="both", expand=True)

        self.informar(f"Conectado a {db.descripcion}")
        self.menu.elegir("inicio")

    # ------------------------------------------------------------------
    @staticmethod
    def _secciones():
        """Opciones del menú lateral: Inicio, las tablas principales del catálogo y Reportes."""
        secciones = [("", [("inicio", "Inicio")])]
        for titulo, tablas in MENU:
            secciones.append((titulo, [(f"tabla:{t}", POR_TABLA[t].titulo) for t in tablas]))
        secciones.append(("Consultas", [("reportes", "Reportes")]))
        return secciones

    def _barra_de_menus(self):
        barra = tk.Menu(self.raiz)
        archivo = tk.Menu(barra, tearoff=False)
        archivo.add_command(label="Actualizar pantalla", accelerator="F5", command=self.refrescar)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.salir)
        barra.add_cascade(label="Archivo", menu=archivo)
        ayuda = tk.Menu(barra, tearoff=False)
        ayuda.add_command(label="Acerca de…", command=self.acerca_de)
        barra.add_cascade(label="Ayuda", menu=ayuda)
        self.raiz.configure(menu=barra)
        self.raiz.bind("<F5>", lambda e: self.refrescar())

    def _mostrar(self, clave):
        """Muestra la pantalla de una opción del menú (la crea la primera vez)."""
        pantalla = self.pantallas.get(clave)
        if pantalla is None:
            pantalla = self._crear(clave)
            self.pantallas[clave] = pantalla
        if self.actual is not pantalla:
            if self.actual is not None:
                self.actual.pack_forget()
            pantalla.pack(fill="both", expand=True)
            self.actual = pantalla
            pantalla.cargar()  # datos al día cada vez que se entra a la pantalla
        return pantalla

    def _crear(self, clave):
        if clave == "inicio":
            return PanelInicio(self.contenedor, self.db, self.abrir_reporte)
        if clave == "reportes":
            return PantallaReportes(self.contenedor, self.db, self.informar)
        entidad = POR_TABLA[clave.split(":", 1)[1]]
        return PantallaEntidad(self.contenedor, entidad, self.db, self.informar)

    # ------------------------------------------------------------------
    def abrir_reporte(self, codigo: str):
        """Va a la pantalla de reportes y abre uno (lo usan las tarjetas de Inicio)."""
        self.menu.elegir("reportes")
        self.pantallas["reportes"].mostrar_reporte(codigo)

    def refrescar(self):
        if self.actual is not None:
            self.actual.cargar()

    def informar(self, texto: str):
        self.estado.configure(text=texto)

    def acerca_de(self):
        messagebox.showinfo(
            "Acerca de",
            f"{NOMBRE}\nVersión {VERSION}\n\n"
            "Aplicativo de demostración de la base de datos bd_licitaciones.\n"
            "Python + Tkinter + PostgreSQL (psycopg).\n\n"
            "Las altas, cambios y bajas se hacen con procedimientos almacenados;\n"
            "las reglas de negocio y la bitácora, con triggers.\n\n"
            f"Conexión: {self.db.descripcion}",
            parent=self.raiz)

    def salir(self):
        self.db.cerrar()
        self.raiz.destroy()
