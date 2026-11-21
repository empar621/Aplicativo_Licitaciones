"""Tabla de datos reutilizable (ttk.Treeview con barras de desplazamiento).

Funciones: filas alternadas, ordenar al hacer clic en un encabezado, filtro
de texto y acceso a la fila seleccionada como diccionario con los valores
originales (no el texto formateado).

Ancho de las columnas (se recalcula al cargar datos y al cambiar el tamaño):
    1. Cada columna pide el ancho que necesita su contenido más largo (o su
       encabezado), con un mínimo y un máximo.
    2. Si la suma es MENOR que el ancho disponible, el espacio sobrante se
       reparte entre todas en proporción: la tabla ocupa todo el ancho y
       ninguna columna queda desproporcionada.
    3. Si la suma es MAYOR, primero ceden espacio las columnas de texto largo
       (objeto, dirección...) hasta un piso; así las tablas medianas caben
       sin barra horizontal.
    4. Si aun así no caben, cada columna conserva su ancho completo y aparece
       la barra de desplazamiento horizontal: ninguna columna queda cortada.
Las barras de desplazamiento solo se muestran cuando hacen falta. El texto
que no cabe en su celda termina en «…» y se muestra completo al detener el
puntero sobre ella.
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from . import estilo, formato

ANCHO_MINIMO = 64     # píxeles de diseño (a 96 ppp)
ANCHO_MAXIMO = 380
ANCHO_ELASTICO = 250  # desde este ancho una columna se considera de texto largo...
PISO_ELASTICO = 180   # ...y puede reducirse hasta aquí para evitar la barra horizontal
FILAS_PARA_MEDIR = 400


class TablaDatos(ttk.Frame):
    """Muestra filas (diccionarios) en columnas."""

    def __init__(self, padre, al_doble_clic=None, al_seleccionar=None, filas_visibles=10,
                 etiquetar=None):
        """
        al_doble_clic   función sin argumentos (doble clic o Enter sobre una fila)
        al_seleccionar  función sin argumentos (cambió la fila seleccionada)
        filas_visibles  alto inicial de la tabla, en filas
        etiquetar       función(fila) -> nombre de etiqueta de color o None
        """
        super().__init__(padre)
        self.arbol = ttk.Treeview(self, show="headings", selectmode="browse", height=filas_visibles)
        self.barra_v = ttk.Scrollbar(self, orient="vertical", command=self.arbol.yview)
        self.barra_h = ttk.Scrollbar(self, orient="horizontal", command=self.arbol.xview)
        self.arbol.configure(yscrollcommand=lambda a, b: self._mover_barra(self.barra_v, a, b),
                             xscrollcommand=lambda a, b: self._mover_barra(self.barra_h, a, b))
        self.arbol.grid(row=0, column=0, sticky="nsew")
        self.barra_v.grid(row=0, column=1, sticky="ns")
        self.barra_h.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.arbol.tag_configure("par", background=estilo.FILA_ALTERNA)
        self.arbol.bind("<Configure>", lambda e: self._ajustar_anchos())
        self.arbol.bind("<ButtonRelease-1>",
                        lambda e: self.after_idle(self._poner_puntos_suspensivos), add="+")
        if al_doble_clic:
            self.arbol.bind("<Double-1>",
                            lambda e: al_doble_clic() if self.arbol.identify_row(e.y) else None)
            self.arbol.bind("<Return>", lambda e: al_doble_clic())
        if al_seleccionar:
            self.arbol.bind("<<TreeviewSelect>>", lambda e: al_seleccionar())

        self._fuente = tkfont.Font(family=estilo.FUENTE, size=10)
        self._fuente_encabezado = tkfont.Font(family=estilo.FUENTE, size=9, weight="bold")
        self._etiquetar = etiquetar
        self.columnas = []        # [(nombre, encabezado)]
        self.filas = []           # todas las filas (dict)
        self.visibles = {}        # iid -> fila
        self._naturales = []      # ancho que pide cada columna
        self._texto_mas_ancho = {}  # columna -> píxeles de su texto más largo
        self._recortadas = set()  # columnas que ahora muestran algún texto con «…»
        self._filtro = ""
        self._orden = (None, False)
        self._ayuda = _TextoCompleto(self)

    # ------------------------------------------------------------------
    # Columnas y datos
    # ------------------------------------------------------------------
    def configurar_columnas(self, columnas):
        """columnas: lista de (nombre, encabezado)."""
        self.columnas = [(c[0], c[1]) for c in columnas]
        nombres = [c[0] for c in self.columnas]
        self.arbol.configure(columns=nombres, displaycolumns=nombres)
        for nombre, titulo in self.columnas:
            self.arbol.heading(nombre, text=titulo, command=lambda n=nombre: self.ordenar_por(n))
            # stretch=False: los anchos los decide _ajustar_anchos, no el Treeview
            self.arbol.column(nombre, minwidth=estilo.px(self, 40), stretch=False)
        self._orden = (None, False)
        self._medir()

    def columnas_de_consulta(self, nombres):
        """Columnas a partir de los nombres que devuelve una consulta (reportes)."""
        self.configurar_columnas([(n, formato.encabezado(n)) for n in nombres])

    def cargar(self, filas):
        """Reemplaza las filas mostradas."""
        self.filas = list(filas)
        columna, descendente = self._orden
        if columna:
            self.filas.sort(key=lambda f: formato.clave_orden(f.get(columna)), reverse=descendente)
        self._medir()
        self._fijar_anchos()
        self._dibujar()

    def filtrar(self, texto: str):
        """Muestra solo las filas que contienen el texto en alguna columna visible."""
        self._filtro = texto.strip().lower()
        self._dibujar()

    def ordenar_por(self, columna):
        anterior, descendente = self._orden
        descendente = not descendente if anterior == columna else False
        self._orden = (columna, descendente)
        self.filas.sort(key=lambda f: formato.clave_orden(f.get(columna)), reverse=descendente)
        for nombre, titulo in self.columnas:
            flecha = (" ▼" if descendente else " ▲") if nombre == columna else ""
            self.arbol.heading(nombre, text=titulo + flecha)
        self._dibujar()

    def _dibujar(self):
        seleccion = self.seleccion()
        self._ayuda.ocultar()
        self.arbol.delete(*self.arbol.get_children())
        self.visibles = {}
        nombres = [c[0] for c in self.columnas]
        for fila in self.filas:
            textos = [formato.a_texto(fila.get(n)) for n in nombres]
            if self._filtro and not any(self._filtro in t.lower() for t in textos):
                continue
            etiquetas = ["par"] if len(self.visibles) % 2 else []
            if self._etiquetar and (color := self._etiquetar(fila)):
                etiquetas.append(color)
            iid = self.arbol.insert("", "end", values=textos, tags=etiquetas)
            self.visibles[iid] = fila
        self._recortadas.clear()            # las celdas recién dibujadas tienen el texto completo
        self._poner_puntos_suspensivos()
        if seleccion is not None:
            self.seleccionar(lambda f: f is seleccion)

    # ------------------------------------------------------------------
    # Ancho de columnas
    # ------------------------------------------------------------------
    def _medir(self):
        """Calcula el ancho que pide cada columna y alinea los números a la derecha."""
        relleno_celda = estilo.px(self, 18)
        relleno_encabezado = estilo.px(self, 30)   # deja sitio a la flecha de orden
        minimo, maximo = estilo.px(self, ANCHO_MINIMO), estilo.px(self, ANCHO_MAXIMO)
        self._naturales = []
        self._texto_mas_ancho = {}
        muestra = self.filas[:FILAS_PARA_MEDIR]
        for nombre, titulo in self.columnas:
            ancho = self._fuente_encabezado.measure(titulo) + relleno_encabezado
            mas_ancho = 0
            for fila in muestra:
                texto = formato.a_texto(fila.get(nombre))
                if texto:
                    mas_ancho = max(mas_ancho, self._fuente.measure(texto))
            self._texto_mas_ancho[nombre] = mas_ancho
            ancho = max(ancho, mas_ancho + relleno_celda)
            self._naturales.append(min(max(ancho, minimo), maximo))

            ejemplo = next((f.get(nombre) for f in muestra if f.get(nombre) is not None), None)
            lado = "e" if formato.es_numero(ejemplo) else "w"
            self.arbol.column(nombre, anchor=lado)
            self.arbol.heading(nombre, anchor=lado)

    def _ajustar_anchos(self):
        """Cambió el tamaño de la tabla: recalcula anchos y recortes de texto."""
        self._fijar_anchos()
        self._poner_puntos_suspensivos()

    def _fijar_anchos(self):
        """Reparte el ancho disponible entre las columnas (ver el encabezado del módulo)."""
        if not self.columnas or self.arbol.winfo_width() <= 1:       # aún sin tamaño en pantalla
            return
        disponible = self.arbol.winfo_width() - estilo.px(self, 4)   # bordes del Treeview
        anchos = list(self._naturales)
        total = sum(anchos)
        if total < disponible:
            # Sobra espacio: se reparte en proporción entre todas las columnas
            anchos = [ancho * disponible // total for ancho in anchos]
            anchos[-1] += disponible - sum(anchos)                   # resto del redondeo
        elif total > disponible:
            # Falta espacio: primero ceden las columnas de texto largo (hasta su piso);
            # si no alcanza, se deja el ancho completo y aparece la barra horizontal.
            pisos = [self._piso(ancho) for ancho in anchos]
            holgura = total - sum(pisos)
            falta = total - disponible
            if 0 < falta <= holgura:
                anchos = [ancho - (ancho - piso) * falta // holgura
                          for ancho, piso in zip(anchos, pisos)]
                mas_ancha = max(range(len(anchos)), key=anchos.__getitem__)
                anchos[mas_ancha] -= sum(anchos) - disponible        # resto del redondeo
        for (nombre, _), ancho in zip(self.columnas, anchos):
            self.arbol.column(nombre, width=ancho)

    def _piso(self, natural: int) -> int:
        """Ancho mínimo al que puede reducirse una columna para evitar la barra horizontal.

        Solo ceden las columnas de texto largo (objeto, dirección, razón
        social...); las de códigos, fechas y números conservan su ancho.
        """
        if natural < estilo.px(self, ANCHO_ELASTICO):
            return natural
        return max(estilo.px(self, PISO_ELASTICO), natural // 2)

    def _poner_puntos_suspensivos(self):
        """Termina en «…» el texto que no cabe en su columna (el completo se ve con el puntero)."""
        relleno = estilo.px(self, 14)
        for nombre, _ in self.columnas:
            ancho = self.arbol.column(nombre, "width") - relleno
            if self._texto_mas_ancho.get(nombre, 0) <= ancho and nombre not in self._recortadas:
                continue                                             # todo cabe y nada que restaurar
            recortada = False
            for iid, fila in self.visibles.items():
                completo = formato.a_texto(fila.get(nombre))
                visible = self._recortar(completo, ancho)
                recortada = recortada or visible != completo
                self.arbol.set(iid, nombre, visible)
            self._recortadas.discard(nombre)
            if recortada:
                self._recortadas.add(nombre)

    def _recortar(self, texto: str, ancho: int) -> str:
        """Devuelve el texto, o su comienzo más «…» si no cabe en `ancho` píxeles."""
        if self._fuente.measure(texto) <= ancho:
            return texto
        minimo, maximo = 0, len(texto)
        while minimo < maximo:                                       # búsqueda binaria del corte
            medio = (minimo + maximo + 1) // 2
            if self._fuente.measure(texto[:medio].rstrip() + "…") <= ancho:
                minimo = medio
            else:
                maximo = medio - 1
        return texto[:minimo].rstrip() + "…"

    def texto_completo(self, iid, nombre) -> str:
        """Texto sin recortar de una celda."""
        fila = self.visibles.get(iid)
        return formato.a_texto(fila.get(nombre)) if fila else ""

    def _mover_barra(self, barra, inicio, fin):
        """Muestra la barra de desplazamiento solo si hay algo que desplazar."""
        if float(inicio) <= 0.0 and float(fin) >= 1.0:
            barra.grid_remove()
        else:
            barra.grid()
        barra.set(inicio, fin)

    # ------------------------------------------------------------------
    # Selección
    # ------------------------------------------------------------------
    def seleccion(self) -> dict | None:
        """Fila seleccionada (valores originales) o None."""
        elegidos = self.arbol.selection()
        return self.visibles.get(elegidos[0]) if elegidos else None

    def seleccionar(self, condicion) -> bool:
        """Selecciona la primera fila que cumple condicion(fila)."""
        for iid, fila in self.visibles.items():
            if condicion(fila):
                self.arbol.selection_set(iid)
                self.arbol.focus(iid)
                self.arbol.see(iid)
                return True
        return False

    def seleccionar_primera(self) -> bool:
        return self.seleccionar(lambda fila: True)

    @property
    def cantidad_visible(self) -> int:
        return len(self.visibles)


class _TextoCompleto:
    """Muestra el texto completo de una celda recortada al detener el puntero sobre ella."""

    ESPERA_MS = 450

    def __init__(self, tabla: TablaDatos):
        self.tabla = tabla
        self.arbol = tabla.arbol
        self.ventana = None
        self._celda = None       # (iid, columna) bajo el puntero
        self._tarea = None
        self.arbol.bind("<Motion>", self._al_mover, add="+")
        for evento in ("<Leave>", "<ButtonPress>", "<MouseWheel>"):
            self.arbol.bind(evento, lambda e: self.ocultar(), add="+")

    def _al_mover(self, evento):
        celda = None
        if self.arbol.identify_region(evento.x, evento.y) == "cell":
            iid = self.arbol.identify_row(evento.y)
            columna = self.arbol.identify_column(evento.x)      # "#3"
            if iid and columna:
                celda = (iid, columna)
        if celda == self._celda:
            return
        self.ocultar()
        self._celda = celda
        if celda:
            self._tarea = self.arbol.after(self.ESPERA_MS, lambda: self._mostrar(*celda))

    def _mostrar(self, iid, columna):
        self._tarea = None
        if not self.arbol.exists(iid):
            return
        nombre = self.arbol.column(columna, "id")
        texto = self.tabla.texto_completo(iid, nombre)
        if texto == self.arbol.set(iid, nombre):
            return                                            # se ve completo: no hace falta
        caja = self.arbol.bbox(iid, columna)
        if not caja:
            return
        x = self.arbol.winfo_rootx() + caja[0]
        y = self.arbol.winfo_rooty() + caja[1] + caja[3] + 2
        self.ventana = tk.Toplevel(self.arbol)
        self.ventana.wm_overrideredirect(True)
        self.ventana.attributes("-topmost", True)
        tk.Label(self.ventana, text=texto, justify="left", wraplength=estilo.px(self.arbol, 520),
                 background="#FFFFFF", foreground="#24303F", relief="solid", borderwidth=1,
                 padx=8, pady=5, font=(estilo.FUENTE, 10)).pack()
        self.ventana.wm_geometry(f"+{x}+{y}")

    def ocultar(self):
        if self._tarea:
            self.arbol.after_cancel(self._tarea)
            self._tarea = None
        if self.ventana is not None:
            self.ventana.destroy()
            self.ventana = None
        self._celda = None
