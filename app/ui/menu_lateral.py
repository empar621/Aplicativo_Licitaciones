"""Menú lateral de la ventana principal.

Una lista corta de opciones agrupadas en secciones. El ancho se calcula a
partir del texto más largo, así ninguna opción se muestra cortada.
"""

import tkinter as tk
from tkinter import font as tkfont

from .. import NOMBRE
from . import estilo

COLOR_TEXTO = "#E3ECF5"
COLOR_SECCION = "#9DB6CF"
COLOR_MARCA = "#9CC3E6"      # barra vertical de la opción elegida


class MenuLateral(tk.Frame):
    """Columna azul con el nombre del aplicativo y las opciones de navegación."""

    def __init__(self, padre, secciones, al_elegir):
        """
        secciones  lista de (título de sección, [(clave, texto), ...]); título "" = sin rótulo
        al_elegir  función(clave) que muestra la pantalla elegida
        """
        super().__init__(padre, background=estilo.AZUL)
        self.al_elegir = al_elegir
        self.opciones = {}     # clave -> (fila, marca, etiqueta)
        self.elegida = None

        fuente_titulo = tkfont.Font(family=estilo.FUENTE, size=13, weight="bold")
        fuente_opcion = tkfont.Font(family=estilo.FUENTE, size=10)
        fuente_seccion = tkfont.Font(family=estilo.FUENTE, size=8, weight="bold")
        margen = estilo.px(self, 18)

        tk.Label(self, text=NOMBRE, font=fuente_titulo, background=estilo.AZUL,
                 foreground=estilo.BLANCO, anchor="w", padx=margen).pack(
            fill="x", pady=(estilo.px(self, 18), estilo.px(self, 14)))
        tk.Frame(self, background=estilo.AZUL_SUAVE, height=1).pack(fill="x")

        ancho_texto = fuente_titulo.measure(NOMBRE)
        for titulo, opciones in secciones:
            if titulo:
                tk.Label(self, text=titulo.upper(), font=fuente_seccion, background=estilo.AZUL,
                         foreground=COLOR_SECCION, anchor="w", padx=margen).pack(
                    fill="x", pady=(estilo.px(self, 18), estilo.px(self, 4)))
            else:
                tk.Frame(self, background=estilo.AZUL, height=estilo.px(self, 10)).pack(fill="x")
            for clave, texto in opciones:
                self._opcion(clave, texto, fuente_opcion, margen)
                ancho_texto = max(ancho_texto, fuente_opcion.measure(texto))

        # Ancho fijo calculado: el texto más largo + márgenes
        self.configure(width=ancho_texto + 2 * margen + estilo.px(self, 12))
        self.pack_propagate(False)

    def _opcion(self, clave, texto, fuente, margen):
        fila = tk.Frame(self, background=estilo.AZUL, cursor="hand2")
        fila.pack(fill="x")
        marca = tk.Frame(fila, background=estilo.AZUL, width=estilo.px(self, 4))
        marca.pack(side="left", fill="y")
        etiqueta = tk.Label(fila, text=texto, font=fuente, background=estilo.AZUL,
                            foreground=COLOR_TEXTO, anchor="w", padx=margen - estilo.px(self, 4),
                            pady=estilo.px(self, 7))
        etiqueta.pack(side="left", fill="x", expand=True)
        self.opciones[clave] = (fila, marca, etiqueta)
        for widget in (fila, etiqueta):
            widget.bind("<Button-1>", lambda e, c=clave: self.elegir(c))
            widget.bind("<Enter>", lambda e, c=clave: self._pintar(c, encima=True))
            widget.bind("<Leave>", lambda e, c=clave: self._pintar(c, encima=False))

    def _pintar(self, clave, encima=False):
        fila, marca, etiqueta = self.opciones[clave]
        if clave == self.elegida:
            fondo, color_marca, color = estilo.AZUL_MEDIO, COLOR_MARCA, estilo.BLANCO
        elif encima:
            fondo, color_marca, color = estilo.AZUL_SUAVE, estilo.AZUL_SUAVE, estilo.BLANCO
        else:
            fondo, color_marca, color = estilo.AZUL, estilo.AZUL, COLOR_TEXTO
        fila.configure(background=fondo)
        marca.configure(background=color_marca)
        etiqueta.configure(background=fondo, foreground=color)

    def elegir(self, clave):
        """Marca una opción como elegida y avisa a la ventana principal."""
        anterior, self.elegida = self.elegida, clave
        if anterior:
            self._pintar(anterior)
        self._pintar(clave)
        self.al_elegir(clave)
