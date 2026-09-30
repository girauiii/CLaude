"""Construye la discusión de resultados (Word y Markdown) de la práctica BC.

Uso:
    python construir_documento.py ruta/a/v3009_v1.xlsx

Genera, en la carpeta informe_BC:
    discusion_resultados_BC.docx
    discusion_resultados_BC.md

Las figuras deben existir antes (las genera analisis_BC.py). Las tablas se
rellenan con los valores calculados a partir de la hoja; el texto contiene los
valores ya redondeados.

Marcado dentro del texto: **negrita**, *cursiva*, _{subíndice}, ^{superíndice}.
"""

import re
import sys
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analisis_BC import derived, load, sensitivity_Qmean, wilson  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
FIG = BASE / "figuras"

# ------------------------------------------------------------ formato numérico


def es(x, dec=0):
    """Número con coma decimal y punto de millares; signo menos tipográfico."""
    s = f"{abs(x):,.{dec}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return ("−" if x < 0 else "") + s


def es_r(a, b, dec=0, step=None):
    if step:
        a, b = round(a / step) * step, round(b / step) * step
    return f"{es(a, dec)}–{es(b, dec)}"


def sci(x, dec=1):
    """1,4·10^{−4} (con marcado de superíndice)."""
    if x == 0:
        return "0"
    e = int(np.floor(np.log10(abs(x))))
    m = x / 10 ** e
    if round(abs(m), dec) >= 10:
        m, e = m / 10, e + 1
    return f"{es(m, dec)}·10^{{{'−' if e < 0 else ''}{abs(e)}}}"


def sci_r(a, b, dec=1):
    return f"{sci(a, dec)} a {sci(b, dec)}"


# ---------------------------------------------------------------- datos


def datos(xlsx):
    data = load(xlsx)
    fits = wilson(data)
    der = derived(data, fits)
    sens = sensitivity_Qmean(data)
    return data, fits, der, sens


NOMBRE = {
    "INT1 f200": "INT 1, fría 200 L/h",
    "INT1 f150": "INT 1, fría 150 L/h",
    "INT2 f150": "INT 2, fría 150 L/h",
    "INT2 f200": "INT 2, fría 200 L/h",
}


def tabla_wilson(data, fits, der):
    header = ["Serie", "Puntos", "Pendiente m (K/W)", "C_{2} (K/W)", "R²",
              "C_{1} = 1/m (W/K)", "h_{i}^{W} (W/(m²·K))"]
    rows, italic = [], []

    def fila(nombre, f, hW, n):
        return [nombre, str(n), f"{es(f['m'], 2)} ± {es(f['se_m'], 2)}",
                es(f["C2"], 5), es(f["R2"], 2), es(f["C1"], 3),
                es_r(hW.min(), hW.max(), step=10)]

    for key in ["INT1 f200", "INT1 f150"]:
        rows.append(fila(NOMBRE[key], fits[key], der[key]["hW"], fits[key]["n"]))
    f8 = fits["INT1 f150 8p"]
    rows.append(fila("INT 1, fría 150 L/h, sin 111 ni 112a", f8,
                     der["INT1 f150 8p"]["hW"], f8["n"]))
    italic.append(len(rows) - 1)
    for key in ["INT2 f150", "INT2 f200"]:
        rows.append(fila(NOMBRE[key], fits[key], der[key]["hW"], fits[key]["n"]))
    return header, rows, italic


def tabla_st(data, der):
    header = ["Serie", "Re", "h_{i,ST} (W/(m²·K))", "h_{i}^{W} (W/(m²·K))",
              "h_{i}^{W}/h_{i,ST}", "R_{f} (m²·K/W)"]
    rows, italic = [], []

    def fila(nombre, s, d):
        return [nombre, es_r(s["Re"].min(), s["Re"].max(), step=10),
                es_r(s["hST"].min(), s["hST"].max(), step=10),
                es_r(d["hW"].min(), d["hW"].max(), step=10),
                es_r(d["ratio"].min(), d["ratio"].max(), 2),
                sci_r(d["Rf"].min(), d["Rf"].max())]

    for key in ["INT1 f200", "INT1 f150"]:
        rows.append(fila(NOMBRE[key], data[key], der[key]))
    rows.append(fila("INT 1, fría 150 L/h, sin 111 ni 112a", data["INT1 f150"],
                     der["INT1 f150 8p"]))
    italic.append(len(rows) - 1)
    for key in ["INT2 f150", "INT2 f200"]:
        rows.append(fila(NOMBRE[key], data[key], der[key]))
    return header, rows, italic


def tabla_comparacion(data, fits, der):
    def rango(keys, campo, fuente="data", dec=0, step=None, factor=1.0):
        vals = np.concatenate([(data[k] if fuente == "data" else der[k])[campo] * factor
                               for k in keys])
        return es_r(vals.min(), vals.max(), dec, step)

    i1, i2 = ["INT1 f200", "INT1 f150"], ["INT2 f150", "INT2 f200"]
    header = ["Magnitud", "INT 1: doble tubo", "INT 2: carcasa y tubos"]
    rows = [
        ["Área exterior A_{o} (m²)", es(np.pi * 0.010 * 4, 4), es(5 * np.pi * 0.008, 4)],
        ["Tubos del lado caliente", "1 tubo de 4 m", "5 tubos de 1 m [1 paso, a confirmar]"],
        ["Velocidad interior (m/s)", rango(i1, "v", dec=2), rango(i2, "v", dec=2)],
        ["Re interior", rango(i1, "Re", step=10), rango(i2, "Re", step=10)],
        ["Calor cedido Q̇_{c} (kW)", rango(i1, "Qc", dec=1, factor=1e-3),
         rango(i2, "Qc", dec=1, factor=1e-3)],
        ["U_{o} (W/(m²·K))", rango(i1, "Uo", step=10), rango(i2, "Uo", step=10)],
        ["Peso de la película interior en 1/UA (%)",
         rango(i1, "frac_in", "der", factor=100), rango(i2, "frac_in", "der", factor=100)],
        ["R² de Wilson (fría 200 / 150 L/h)",
         f"{es(fits['INT1 f200']['R2'], 2)} / {es(fits['INT1 f150']['R2'], 2)}",
         f"{es(fits['INT2 f200']['R2'], 2)} / {es(fits['INT2 f150']['R2'], 2)}"],
        ["C_{1} (W/K) (fría 200 / 150 L/h)",
         f"{es(fits['INT1 f200']['C1'], 3)} / {es(fits['INT1 f150']['C1'], 3)}",
         f"{es(fits['INT2 f200']['C1'], 3)} / {es(fits['INT2 f150']['C1'], 3)}"],
        ["h_{i}^{W} (W/(m²·K))", rango(i1, "hW", "der", step=10), rango(i2, "hW", "der", step=10)],
        ["h_{i,ST} (W/(m²·K))", rango(i1, "hST", step=10), rango(i2, "hST", step=10)],
        ["h_{i}^{W}/h_{i,ST}", rango(i1, "ratio", "der", dec=2), rango(i2, "ratio", "der", dec=2)],
        ["R_{f} (m²·K/W)", "Negativo: no determinable",
         f"{sci(min(der[k]['Rf'].min() for k in i2))} a "
         f"{sci(max(der[k]['Rf'].max() for k in i2))} (aparente)"],
        ["NTU", rango(i1, "NTU", "der", dec=2), rango(i2, "NTU", "der", dec=2)],
        ["Eficiencia ε", rango(i1, "eps", dec=2), rango(i2, "eps", dec=2)],
    ]
    return header, rows, []


# ---------------------------------------------------------------- contenido

NOTAS = [
    ("p", "Este texto sustituye a la sección 3 del borrador. Usa los valores de la hoja "
          "v3009_v1.xlsx con una excepción: la recta de Wilson del INT 1 con agua fría a "
          "150 L/h se calcula con los diez puntos (filas 14–23), como indicaba el borrador. "
          "Los valores entre corchetes [ ] se deben completar o confirmar."),
    ("p", "**Cambios necesarios en la hoja para que coincida con el texto**"),
    ("bullets", [
        "«INT 1», celdas AC16:AC18 (pendiente, ordenada y R²): usar las filas 14–23 en lugar "
        "de 16–23. Con ello cambian C_{1} (AC20), h_{i}^{W} (AA14:AA23) y R_{f} (AL14:AL23).",
        "«Rf vs Caudal caliente»: los valores están pegados, no enlazados. Hay que actualizar "
        "a mano E16:E25 (INT 1 con agua fría a 150 L/h).",
        "«INT 2», celda AL2, y «Rf vs Caudal caliente», celda H3: la unidad de R_{f} es "
        "m²·K/W, no W/(m²·K).",
    ]),
    ("p", "**Cálculos del texto que no están en la hoja.** Si se mantienen en el informe, "
          "conviene reproducirlos en el Excel. El script analisis_BC.py los calcula todos."),
    ("bullets", [
        "Error típico de las pendientes de Wilson e intervalo de confianza del 95 %.",
        "Rectas de Wilson con UA calculado con la media de Q̇_{c} y Q̇_{f} (prueba de "
        "sensibilidad).",
        "Coeficiente exterior equivalente, h_{o} ≈ 1/(C_{2}·A_{o}), y peso de la película "
        "interior en la resistencia total, (1/C_{1})·Re^{−0,8}/(1/UA).",
        "Re del espacio anular del INT 1 (D_{h} = 10 mm; viscosidad del agua con una "
        "correlación de tipo Vogel, μ = 2,414·10^{−5}·10^{247,8/(T − 140)} Pa·s).",
        "Corrección de ΔT_{c} necesaria para cerrar el balance, NTU y C_{r}, y la "
        "estimación de (μ/μ_{w})^{0,14}.",
    ]),
    ("p", "**Pendiente de confirmar**"),
    ("bullets", [
        "Precisión de las sondas de temperatura.",
        "Criterio de repetición (10 % u 11 %). Tras las repeticiones quedan siete puntos con "
        "|δ| > 10 % y dos con |δ| > 11 % (INT 2 con agua fría a 200 L/h, a 300 y 400 L/h).",
        "Número de pasos por tubos del INT 2 (se supone un solo paso con los cinco tubos en "
        "paralelo) y si la carcasa tiene deflectores.",
        "Si los rotámetros están calibrados para agua.",
        "Qué Q̇ usar para calcular UA (Q̇_{c}, Q̇_{f} o la media): consultar con el profesor.",
        "Referencias de las correlaciones de conductividad de la hoja EC1 (Ramires et al., "
        "1995, para el agua; «Deng y Zhang» para el etilenglicol): hay que añadir los datos "
        "completos a la bibliografía. No he podido verificar la segunda.",
    ]),
    ("p", "**Figuras y numeración.** Las figuras se han rehecho en castellano con los mismos "
          "colores que el borrador, salvo la serie INT 2 con agua fría a 200 L/h, que pasa de "
          "azul marino a violeta para distinguirla mejor. Se mantiene la numeración del "
          "borrador (Ec. 1–14, y Tabla 1 y Figura 1 en la sección 2). La nueva Figura 5 "
          "(h_{i} y R_{f}) hace que la de eficiencia pase a ser la Figura 6. La sección 4 "
          "(Conclusiones) debe actualizarse con los resultados de R_{f}."),
]


def contenido(data, fits, der):
    return [
        ("h2", "3. Resultados y discusión"),
        ("p", "Los balances de energía cierran dentro de ±12 % y los coeficientes globales "
              "están, en su mayoría, en el rango típico de un intercambiador agua-agua. El "
              "método de Wilson da resultados coherentes en el INT 2, pero no en el INT 1, por "
              "un motivo físico que se explica en el apartado 3.3. En consecuencia, el factor "
              "de ensuciamiento solo puede estimarse en el INT 2, y aun así debe interpretarse "
              "como un valor aparente (apartado 3.4)."),

        ("h3", "3.1 Balance de energía"),
        ("p", "La desviación del balance (Ec. 3) se mantiene entre −11,1 % y +11,8 % en los 40 "
              "puntos (Figura 2). La media de cada serie va de −4,7 % (INT 1, agua fría a "
              "200 L/h) a +1,0 % (INT 2, agua fría a 200 L/h), con desviaciones típicas de 5 a "
              "9 puntos porcentuales."),
        ("fig", "fig2_balance.png", 16.0,
         "Figura 2. Desviación del balance de energía (Ec. 3) en función del caudal caliente."),
        ("p", "La desviación no es aleatoria, sino que depende del caudal caliente. A 150 y "
              "200 L/h es positiva en los ocho puntos (Q̇_{c} > Q̇_{f}), lo que es coherente "
              "con pérdidas de calor al ambiente. A partir de 250 L/h predominan las "
              "desviaciones negativas (25 de 32 puntos): el agua fría gana más calor del que "
              "cede el corriente caliente, algo que las pérdidas no pueden explicar."),
        ("p", "La causa más probable es la medida de ΔT_{c}. Al aumentar el caudal caliente, "
              "el salto térmico de este corriente baja hasta 3,8–5,5 K a 550–600 L/h, mientras "
              "que el del agua fría se mantiene en 12–17 K. Por eso, un mismo error absoluto de "
              "temperatura pesa entre 2,4 y 4,2 veces más en Q̇_{c} que en Q̇_{f}. En los 25 "
              "puntos con δ < 0, bastaría con que ΔT_{c} fuera entre 0,01 y 0,75 K mayor que "
              "el medido para cerrar el balance [comparar con la precisión de las sondas]. El "
              "cambio de signo se explicaría por la combinación de dos efectos: unas pérdidas "
              "aproximadamente constantes, que pesan más a caudal bajo, y un pequeño error "
              "sistemático en ΔT_{c} (por ejemplo, una diferencia de calibración entre las "
              "sondas de entrada y salida del corriente caliente), que pesa más cuanto menor "
              "es ΔT_{c}."),
        ("p", "Los puntos que superaban el criterio de repetición [10 %] se repitieron, y en "
              "el análisis se usan las repeticiones. En el INT 1, las repeticiones difieren de "
              "los puntos originales entre 3 y 22 puntos porcentuales en δ (el mayor cambio, en "
              "el punto 120: de −32,8 % a −10,8 %), lo que sugiere que algunos puntos "
              "originales se tomaron antes de alcanzar el estado estacionario."),
        ("p", "Como UA se calcula con Q̇_{c}, esta tendencia se propaga a los resultados "
              "siguientes: donde δ ≈ −10 %, el UA calculado con Q̇_{f} sería un 10 % mayor. Su "
              "efecto sobre el método de Wilson se analiza en el apartado 3.3."),

        ("h3", "3.2 Coeficiente global"),
        ("p", "El coeficiente global referido al área exterior (U_{o} = UA/A_{o}) aumenta con "
              "el caudal caliente en las cuatro series (Figura 3). En el INT 1 va de 1.090 a "
              "1.580 W/(m²·K), dentro del rango típico agua-agua que da el protocolo "
              "(850–1.700 W/(m²·K)). En el INT 2 va de 560 a 1.350 W/(m²·K), y los puntos con "
              "caudal caliente bajo (hasta 200–300 L/h) quedan por debajo de ese rango."),
        ("fig", "fig3_Uo.png", 16.0,
         "Figura 3. Coeficiente global U_{o} en función del caudal caliente para cada serie."),
        ("p", "Como los dos equipos tienen la misma área exterior (0,1257 m²), la diferencia "
              "se debe a los coeficientes individuales. La respuesta de U_{o} a cada caudal "
              "indica qué película controla la transmisión de calor en cada equipo:"),
        ("bullets", [
            "En el INT 1, cuadruplicar el caudal caliente (de 150 a 600 L/h) solo aumenta "
            "U_{o} un 13–23 %, mientras que pasar el agua fría de 150 a 200 L/h (+33 %) lo "
            "aumenta un 18 % de media. La resistencia dominante es la del lado del agua fría.",
            "En el INT 2, el mismo aumento del caudal caliente duplica U_{o} (×2,0–2,1), y el "
            "aumento del caudal frío lo eleva un 14 % de media. Aquí la película interior "
            "tiene un peso mucho mayor.",
        ]),
        ("p", "Esto es coherente con las condiciones de flujo. Dentro de los tubos del INT 2 la "
              "mezcla circula a 0,29–1,18 m/s (Re = 2.700–11.500), unas 2,8 veces más despacio "
              "que en el tubo del INT 1 (0,83–3,32 m/s; Re = 9.600–42.400), porque el mismo "
              "caudal se reparte entre cinco tubos. En el espacio anular del INT 1, en cambio, "
              "el agua fría circula a solo 0,18–0,24 m/s, con Re ≈ 2.100–2.900 (estimado con el "
              "diámetro hidráulico, 10 mm, y la viscosidad del agua a su temperatura media), es "
              "decir, en régimen laminar o de transición. Esa película exterior es la que "
              "limita el coeficiente global del INT 1."),
        ("p", "Las irregularidades de algunas curvas, como el mínimo del INT 1 a 250 L/h con "
              "agua fría a 150 L/h o el máximo del INT 2 a 550 L/h con agua fría a 200 L/h, son "
              "del orden de la dispersión del balance y no deben interpretarse como efectos "
              "físicos."),

        ("h3", "3.3 Método de Wilson"),
        ("p", "La representación de 1/UA frente a Re^{−0,8} se ajusta a una recta para cada "
              "serie (Figura 4). La Tabla 2 recoge los parámetros de los ajustes, que incluyen "
              "los diez puntos de cada serie. La fila en cursiva es la prueba de sensibilidad "
              "que se comenta más abajo."),
        ("fig", "fig4_wilson.png", 14.5,
         "Figura 4. Rectas de Wilson (Ec. 8) del INT 1 y el INT 2 para los dos caudales de "
         "agua fría. Las ecuaciones están en las unidades escaladas de los ejes. En el INT 1 "
         "se marcan los puntos 111 y 112a y, en trazo discontinuo, el ajuste sin ellos que usa "
         "la hoja v3009_v1."),
        ("table", "wilson",
         "Tabla 2. Parámetros de las rectas de Wilson (Ec. 8) y coeficientes individuales "
         "resultantes (Ec. 9). La incertidumbre de la pendiente es el error típico del "
         "ajuste."),
        ("p", "**INT 2.** Las dos rectas son casi paralelas: C_{1} vale 0,192 y 0,189 W/K, un "
              "2 % de diferencia, tal como prevé el método, ya que la pendiente solo depende "
              "del lado interior. La ordenada C_{2}, que agrupa la pared, el posible "
              "ensuciamiento y la película exterior, baja de 0,00456 a 0,00336 K/W al pasar el "
              "agua fría de 150 a 200 L/h, coherente con una película exterior más favorable. "
              "Si se desprecian la pared y el ensuciamiento, estas ordenadas equivalen a un "
              "coeficiente exterior h_{o} ≈ 1/(C_{2}·A_{o}) de unos 1.750 y 2.370 W/(m²·K). "
              "Como C_{2} incluye también esas otras resistencias, son límites inferiores de "
              "h_{o}."),
        ("p", "**INT 1.** Los ajustes son mucho menos fiables: R² = 0,80 y 0,34, y las C_{1} de "
              "las dos series difieren un 23 %. En la serie con agua fría a 150 L/h, el error "
              "típico de la pendiente es del 49 % y su intervalo de confianza del 95 % incluye "
              "el cero, así que la pendiente no es significativamente distinta de cero. La "
              "causa es física: según los propios ajustes, la película interior solo "
              "representa el 6–25 % de la resistencia total en el INT 1, frente al 39–75 % en "
              "el INT 2. Entre 150 y 600 L/h, 1/UA solo disminuye un 11–19 % en el INT 1 "
              "(un 49–52 % en el INT 2), una variación del mismo orden que la dispersión del "
              "balance (±10 %), que acaba dominando la pendiente. La ordenada, en cambio, sí "
              "se comporta como se espera: C_{2} aumenta de 0,00462 a 0,00573 K/W al bajar el "
              "caudal frío (h_{o} equivalente de 1.720 y 1.390 W/(m²·K))."),
        ("p", "**Sensibilidad a la selección de puntos.** En la hoja v3009_v1, la recta del "
              "INT 1 con agua fría a 150 L/h se calcula sin los puntos 111 y 112a (filas "
              "16–23). Con ese ajuste, R² sube a 0,91, pero C_{1} baja a 0,153 W/K, 3,4 veces "
              "menos que con los diez puntos y 2,8 veces menos que en la otra serie del mismo "
              "equipo. Además, su ordenada (0,00452 K/W) quedaría por debajo de la de la serie "
              "con más caudal frío (0,00462 K/W), al contrario de lo esperado. Los dos puntos "
              "excluidos tienen δ ≈ +9 %, dentro del criterio de repetición, así que no hay un "
              "motivo objetivo para descartarlos, y en este informe se usan los diez puntos. "
              "Que la pendiente cambie un factor 3,4 al quitar dos de diez puntos confirma que "
              "en el INT 1 no está bien determinada."),
        ("p", "**Sensibilidad al calor usado para UA.** Como UA se calcula con Q̇_{c} y δ "
              "varía de forma sistemática con el caudal (apartado 3.1), se ha repetido el "
              "ajuste con UA calculado a partir de la media de Q̇_{c} y Q̇_{f}. En el INT 2, "
              "C_{1} baja un 10 % (0,172 y 0,169 W/K) y las dos series siguen coincidiendo. En "
              "el INT 1, C_{1} pasa a 0,324 y 0,326 W/K: las dos series coinciden entonces en "
              "menos de un 1 %, y R² sube a 0,91 y 0,73. Buena parte de la incoherencia del "
              "INT 1 se debe, por tanto, al error del balance, pero el resultado depende de una "
              "elección (qué Q̇ usar) que no puede justificarse solo con estos datos [consultar "
              "con el profesor]."),
        ("p", "**Régimen de flujo.** La proporcionalidad h_{i} ∝ Re^{0,8} en la que se basa el "
              "método es propia del régimen turbulento. En el INT 1 (Re = 9.600–42.400) se "
              "cumple en casi todos los puntos, pero en el INT 2, 16 de los 20 puntos están en la zona de transición "
              "(2.100 < Re < 10^{4}), así que el método se aplica fuera de su rango habitual, "
              "aunque los puntos se alinean bien. El método supone también que C_{2} es "
              "constante en cada serie, pero la temperatura media del agua fría sube 3–4 K a lo "
              "largo de cada serie, lo que modifica ligeramente sus propiedades y h_{o}."),

        ("h3", "3.4 Correlación de Sieder-Tate y factor de ensuciamiento"),
        ("p", "La conductividad térmica de la mezcla, calculada con una regla de mezcla lineal "
              "en fracción másica, es de 0,580–0,587 W/(m·K), y el número de Prandtl del fluido "
              "caliente, de 4,2–4,8. Según el Re, la Ec. 10 se aplica con C = 0,027 en todos "
              "los puntos del INT 1 salvo el de 150 L/h (Re ≈ 9.600–9.700, C = 0,023), y con "
              "C = 0,023 en el INT 2 salvo los de 550 y 600 L/h. La Tabla 3 y la Figura 5 "
              "comparan h_{i,ST} con h_{i}^{W} y muestran el factor de ensuciamiento "
              "resultante (Ec. 11)."),
        ("table", "st",
         "Tabla 3. Coeficientes individuales de Sieder-Tate y de Wilson, y factor de "
         "ensuciamiento (Ec. 11). Rango de los puntos de cada serie. La fila en cursiva usa el "
         "ajuste de ocho puntos de la hoja v3009_v1."),
        ("fig", "fig5_hi_Rf.png", 14.5,
         "Figura 5. (a) Coeficiente individual de Wilson frente al de Sieder-Tate. (b) Factor "
         "de ensuciamiento aparente (Ec. 11) en función del caudal caliente. La franja "
         "sombreada indica los valores típicos del protocolo."),
        ("p", "**INT 2.** El coeficiente experimental es aproximadamente la mitad del de la "
              "correlación en todo el intervalo: h_{i}^{W}/h_{i,ST} = 0,54–0,56 con Re < 10^{4} "
              "y 0,47–0,48 con Re > 10^{4}. Con la Ec. 11 esto da R_{f} = 1,4·10^{−4} a "
              "4,0·10^{−4} m²·K/W (media de los 20 puntos: 2,2·10^{−4} m²·K/W), del orden de "
              "los valores típicos del protocolo (1·10^{−4} a 10·10^{−4} m²·K/W). Las dos "
              "series, con distinto caudal frío, dan prácticamente el mismo R_{f}, como "
              "corresponde a una magnitud del lado interior."),
        ("p", "Sin embargo, R_{f} no es constante: disminuye con el caudal caliente, de unos "
              "4·10^{−4} m²·K/W a 150 L/h a 1,5·10^{−4} m²·K/W a 600 L/h (Figura 5b), mientras "
              "que el ensuciamiento de los tubos no debería cambiar con el caudal a lo largo "
              "de una sesión de prácticas. La tendencia es una consecuencia del cálculo: como h_{i}^{W} y "
              "h_{i,ST} son proporcionales a Re^{0,8}, su cociente es casi constante, y la "
              "Ec. 11 da R_{f} = (1/h_{i,ST})·(h_{i,ST}/h_{i}^{W} − 1), que disminuye como "
              "Re^{−0,8}. El pequeño aumento de R_{f} entre 500 y 550 L/h tampoco es físico: "
              "coincide con el cambio de C = 0,023 a C = 0,027 en Re = 10^{4}, que aumenta "
              "h_{i,ST} un 17 %."),
        ("p", "Por tanto, hay que matizar la interpretación de R_{f}. Un ensuciamiento "
              "constante aparecería en la ordenada de la recta de Wilson (Ec. 6 y 8), no en la "
              "pendiente de la que se obtiene h_{i}^{W}. Lo que mide la Ec. 11 es la diferencia "
              "entre el coeficiente medido y el de la correlación, que en el INT 2 puede "
              "deberse, además de a depósitos en los tubos, a:"),
        ("bullets", [
            "La aplicación de una correlación de tipo turbulento en la zona de transición, "
            "donde las correlaciones son mucho menos precisas.",
            "Un reparto desigual del caudal entre los cinco tubos: como h_{i} crece menos que "
            "proporcionalmente con la velocidad, el coeficiente medio es menor que el "
            "calculado con la velocidad media.",
            "La geometría supuesta. Si el haz tuviera más de un paso por tubos, la velocidad "
            "real y h_{i,ST} serían mayores, y la diferencia previsiblemente aumentaría.",
            "Las propiedades de la mezcla. Como h_{i,ST} es proporcional a k^{2/3}, un error "
            "del 10 % en la conductividad solo cambia h_{i,ST} un 7 %. La corrección "
            "(μ/μ_{w})^{0,14}, omitida en el cálculo, reduciría h_{i,ST} aproximadamente un "
            "2–4 % en el INT 2 "
            "y un 1 % o menos en el INT 1. Ninguno de estos efectos explica por sí solo un "
            "factor 2.",
        ]),
        ("p", "El R_{f} del INT 2 debe interpretarse, pues, como un factor de ensuciamiento "
              "aparente, que da el orden de magnitud (10^{−4} m²·K/W) pero no permite separar "
              "el ensuciamiento real de la incertidumbre de la correlación."),
        ("p", "**INT 1.** Con los ajustes de diez puntos, h_{i}^{W} es entre 1,3 y 1,9 veces "
              "h_{i,ST} y R_{f} sale negativo (entre −1,1·10^{−4} y −1,5·10^{−5} m²·K/W), lo "
              "que no tiene sentido físico. El signo depende además de las decisiones de "
              "cálculo: con el ajuste de ocho puntos de la hoja v3009_v1, R_{f} sería positivo "
              "(6,8·10^{−5} a 1,9·10^{−4} m²·K/W), y con UA calculado a partir de la media de "
              "Q̇_{c} y Q̇_{f}, h_{i}^{W}/h_{i,ST} = 0,99–1,16 y R_{f} ≈ 0 (entre −3·10^{−5} y "
              "+2·10^{−6} m²·K/W). Como en el INT 1 la película interior pesa poco en la "
              "resistencia total, la diferencia 1/h_{i}^{W} − 1/h_{i,ST} es del mismo orden "
              "que su incertidumbre, y R_{f} no puede determinarse en este equipo con el método "
              "del protocolo."),

        ("h3", "3.5 Eficiencia"),
        ("p", "La eficiencia (Ec. 12, calculada con Q̇_{c}) va de 0,44 a 0,59 en el INT 1 y de "
              "0,30 a 0,52 en el INT 2 (Figura 6). El INT 1 es más eficiente que el INT 2 en "
              "todos los puntos con los mismos caudales."),
        ("fig", "fig6_eficiencia.png", 16.0,
         "Figura 6. Eficiencia (Ec. 12) en función del caudal caliente para cada serie."),
        ("p", "La eficiencia depende de NTU = UA/C_{mín} y de la relación de capacidades "
              "C_{r} = C_{mín}/C_{máx}. La capacidad calorífica del corriente caliente es de "
              "166 W/K a 150 L/h y de 222 W/K a 200 L/h, y la del agua fría, de 174 W/K a "
              "150 L/h y de 232 W/K a 200 L/h. El corriente caliente solo es el de menor "
              "capacidad a 150 L/h (y a 200 L/h cuando el agua fría va a 200 L/h). En el resto "
              "de puntos, C_{mín} corresponde al agua fría y Q̇_{máx} deja de crecer con el "
              "caudal caliente."),
        ("p", "En el INT 2, UA se duplica a lo largo de cada serie y NTU pasa de 0,42–0,44 a "
              "0,66–0,79, por lo que ε crece claramente con el caudal caliente. En el INT 1, UA "
              "varía poco (NTU = 0,76–1,00) y ε se mantiene aproximadamente constante, con un "
              "ligero aumento a caudales altos porque C_{r} disminuye hasta 0,26–0,35. Con "
              "NTU ≤ 1, ninguno de los dos equipos puede superar una eficiencia de "
              "aproximadamente 0,6 en estas condiciones: según la relación ε–NTU de un "
              "intercambiador en contracorriente, llegar a ε = 0,8 exigiría un NTU de aproximadamente 2 o más."),
        ("p", "Hay que tener en cuenta, además, que en los puntos en que C_{mín} es el agua "
              "fría, ε se calcula con Q̇_{c} y con la capacidad del agua fría, así que arrastra "
              "el error del balance: donde δ ≈ −10 %, la eficiencia calculada con Q̇_{f} sería "
              "un 10 % mayor."),

        ("h3", "3.6 Comparación entre intercambiadores"),
        ("table", "comparacion", "Tabla 4. Resumen comparativo de los dos intercambiadores."),
        ("p", "Con la misma área exterior, el INT 1 transfiere más calor (2,3–3,4 kW frente a "
              "1,5–3,2 kW), tiene un U_{o} mayor y es más eficiente en todos los puntos "
              "comparables. La ventaja se debe sobre todo a una velocidad interior 2,8 veces "
              "mayor, y tiene un coste que no se ha medido: con esa velocidad y un tubo cuatro "
              "veces más largo, la pérdida de carga del lado caliente del INT 1 será mucho "
              "mayor. El INT 2, en cambio, es más compacto (tubos de 1 m frente a 4 m)."),
        ("p", "Para mejorar cada equipo habría que actuar sobre la película que controla: en el "
              "INT 1, sobre el lado del agua fría (más caudal o un espacio anular más "
              "estrecho); en el INT 2, sobre el lado de los tubos (más velocidad, por ejemplo "
              "con más pasos por tubos, a costa de más pérdida de carga)."),
        ("p", "Para los objetivos de la práctica, el resultado es el contrario: el INT 2 permite "
              "determinar h_{i} con el método de Wilson de forma fiable, porque la película "
              "interior pesa más en la resistencia total, mientras que en el INT 1 ni h_{i} ni "
              "R_{f} pueden determinarse con precisión."),

        ("h3", "3.7 Fuentes de error y limitaciones"),
        ("bullets", [
            "**Sondas de temperatura.** Con saltos térmicos del corriente caliente de "
            "3,8–5,5 K a caudales altos, un error sistemático inferior a 1 K en ΔT_{c} basta "
            "para explicar desviaciones del −10 % [precisión de las sondas: a confirmar].",
            "**Estado estacionario.** Las repeticiones del INT 1 difieren de los puntos "
            "originales hasta 22 puntos porcentuales en δ, lo que sugiere que en algunos "
            "puntos no se esperó lo suficiente tras cambiar el caudal [criterio y tiempo de "
            "espera].",
            "**Pérdidas al ambiente.** Reducen Q̇_{f} respecto a Q̇_{c} y justifican "
            "desviaciones positivas, pero no las negativas. En los dos equipos el agua fría "
            "circula por fuera, a 21–40 °C, cerca de la temperatura ambiente, por lo que "
            "deberían ser pequeñas [aislamiento del equipo: a confirmar].",
            "**Rotámetros.** Si están calibrados para agua, la lectura del caudal de la mezcla "
            "(densidad un 1,5 % mayor y viscosidad algo mayor) puede necesitar corrección "
            "[a confirmar]. Un error en el caudal caliente afecta a Q̇_{c} y a Re y, a través "
            "de Re, a h_{i,ST}.",
            "**Propiedades.** Las densidades se toman constantes a 25 °C; a 45–50 °C la "
            "densidad de la mezcla es aproximadamente un 1 % menor, lo que sobreestima "
            "ligeramente ṁ_{c}. C_{p}, μ y k de la mezcla se calculan con reglas de mezcla "
            "ideales a partir de datos tabulados [fuente a citar].",
            "**Correlación de Sieder-Tate.** Se ha aplicado sin la corrección "
            "(μ/μ_{w})^{0,14} (efecto del 1–4 %) y, en el INT 2, en la zona de transición, "
            "donde su precisión es baja.",
            "**Geometría.** Se supone que los cinco tubos del INT 2 trabajan en paralelo en un "
            "solo paso y que el flujo global es en contracorriente en los dos equipos, de "
            "modo que ΔT_{ml} no necesita factor de corrección. Si el INT 2 tuviera más de un "
            "paso por tubos, habría que aplicar el factor F a ΔT_{ml} y recalcular la "
            "velocidad y Re [a confirmar].",
            "**Hipótesis del método de Wilson.** Se supone C_{2} constante en cada serie y "
            "h_{i} ∝ Re^{0,8}. La primera solo se cumple aproximadamente y la segunda no es "
            "válida en la zona de transición.",
            "**Cálculo de UA con Q̇_{c}.** Calcular UA con la media de Q̇_{c} y Q̇_{f} cambia "
            "C_{1} un 24–38 % en el INT 1 y un 10 % en el INT 2 (apartado 3.3).",
        ]),
    ]


# ---------------------------------------------------------------- marcado

TOKEN = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*|_\{[^}]*\}|\^\{[^}]*\})")
UNIT = re.compile(r"(?<=\d) (?=(?:L/h|K/W|W/K|W/\(|K\b|kW|°C|%|m²|m/s|m\b|mm|Pa|veces))")


REF = re.compile(r"\b(Ec\.|Tabla|Figura|apartado) (?=\d)")


def nbsp(text):
    text = UNIT.sub("\u00a0", text)
    return REF.sub(lambda m: m.group(1) + "\u00a0", text)


def add_runs(par, text, italic=False, size=None, color=None):
    for tok in TOKEN.split(nbsp(text)):
        if not tok:
            continue
        bold = sub = sup = ital = False
        if tok.startswith("**"):
            tok, bold = tok[2:-2], True
        elif tok.startswith("*"):
            tok, ital = tok[1:-1], True
        elif tok.startswith("_{"):
            tok, sub = tok[2:-1], True
        elif tok.startswith("^{"):
            tok, sup = tok[2:-1], True
        # dentro de negrita puede haber subíndices: se procesan recursivamente
        if bold and TOKEN.search(tok):
            for inner in TOKEN.split(tok):
                if not inner:
                    continue
                r = _run(par, inner, italic, size, color)
                r.bold = True
            continue
        r = par.add_run(tok)
        r.bold = bold or None
        r.italic = (ital or italic) or None
        r.font.subscript = sub or None
        r.font.superscript = sup or None
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = color


def _run(par, tok, italic, size, color):
    sub = sup = False
    if tok.startswith("_{"):
        tok, sub = tok[2:-1], True
    elif tok.startswith("^{"):
        tok, sup = tok[2:-1], True
    r = par.add_run(tok)
    r.italic = italic or None
    r.font.subscript = sub or None
    r.font.superscript = sup or None
    if size:
        r.font.size = Pt(size)
    if color:
        r.font.color.rgb = color
    return r


def to_md(text):
    text = re.sub(r"_\{([^}]*)\}", r"<sub>\1</sub>", text)
    return re.sub(r"\^\{([^}]*)\}", r"<sup>\1</sup>", text)


# ---------------------------------------------------------------- Word

def estilo_documento(doc):
    st = doc.styles
    normal = st["Normal"]
    normal.font.name = "Calibri"
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    normal.font.size = Pt(11)
    pf = normal.paragraph_format
    pf.space_after = Pt(8)
    pf.line_spacing = 1.08
    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)):
        h = st[name]
        h.font.name = "Calibri"
        rpr = h.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        for att in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rfonts.set(qn(att), "Calibri")
        for att in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rfonts.get(qn(att)) is not None:
                del rfonts.attrib[qn(att)]
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.italic = False
        h.font.color.rgb = RGBColor(0, 0, 0)
        h.paragraph_format.space_before = Pt(14 if name != "Heading 3" else 10)
        h.paragraph_format.space_after = Pt(6)
    lb = st["List Bullet"]
    lb.paragraph_format.space_after = Pt(4)


def sombrear(cell, fill="F2F2F2"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def repetir_cabecera(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def no_partir_fila(row):
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))


def tabla_docx(doc, header, rows, italic_rows, caption, widths=None):
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = doc.styles["Table Grid"]
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, text in enumerate(header):
        c = t.rows[0].cells[j]
        c.paragraphs[0].paragraph_format.space_after = Pt(0)
        add_runs(c.paragraphs[0], f"**{text}**" if "_{" not in text and "^{" not in text
                 else text, size=9)
        if "_{" in text or "^{" in text:
            for r in c.paragraphs[0].runs:
                r.bold = True
        sombrear(c)
    repetir_cabecera(t.rows[0])
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            c = t.rows[i + 1].cells[j]
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            add_runs(p, text, italic=(i in italic_rows), size=9)
        no_partir_fila(t.rows[i + 1])
    if widths:
        t.autofit = False
        for j, gc in enumerate(t._tbl.tblGrid.findall(qn("w:gridCol"))):
            gc.set(qn("w:w"), str(int(widths[j] * 567)))
        for row in t.rows:
            for j, w in enumerate(widths):
                row.cells[j].width = Cm(w)
    cap = doc.add_paragraph()
    cap.paragraph_format.space_before = Pt(4)
    add_runs(cap, caption, italic=True, size=10)
    return t


def figura_docx(doc, path, width_cm, caption):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    cap = doc.add_paragraph()
    add_runs(cap, caption, italic=True, size=10)


def construir_docx(bloques, tablas, destino):
    doc = Document()
    estilo_documento(doc)
    sec = doc.sections[0]
    for att in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, att, Cm(2.54))
    props = doc.core_properties
    props.title = "Informe BC: resultados y discusión"
    props.author = ""
    props.comments = ""
    for kind, *args in bloques:
        if kind in ("h1", "h2", "h3"):
            h = doc.add_heading(level=int(kind[1]))
            add_runs(h, args[0])
        elif kind == "p":
            add_runs(doc.add_paragraph(), args[0])
        elif kind == "meta":
            add_runs(doc.add_paragraph(), args[0], color=RGBColor(0x59, 0x59, 0x59))
        elif kind == "bullets":
            for item in args[0]:
                add_runs(doc.add_paragraph(style="List Bullet"), item)
        elif kind == "fig":
            figura_docx(doc, FIG / args[0], args[1], args[2])
        elif kind == "table":
            header, rows, italic, widths = tablas[args[0]]
            tabla_docx(doc, header, rows, italic, args[1], widths)
    doc.save(destino)


# ---------------------------------------------------------------- Markdown

def construir_md(bloques, tablas, destino):
    out = []
    for kind, *args in bloques:
        if kind in ("h1", "h2", "h3"):
            out.append("#" * int(kind[1]) + " " + to_md(args[0]) + "\n")
        elif kind in ("p", "meta"):
            out.append(to_md(args[0]) + "\n")
        elif kind == "bullets":
            out.append("\n".join("- " + to_md(i) for i in args[0]) + "\n")
        elif kind == "fig":
            out.append(f"![{to_md(args[2]).split('.')[0]}](figuras/{args[0]})\n")
            out.append(f"*{to_md(args[2])}*\n")
        elif kind == "table":
            header, rows, italic, _ = tablas[args[0]]
            lines = ["| " + " | ".join(to_md(h) for h in header) + " |",
                     "|" + "---|" * len(header)]
            for i, r in enumerate(rows):
                cells = [to_md(c) for c in r]
                if i in italic:
                    cells = [f"*{c}*" for c in cells]
                lines.append("| " + " | ".join(cells) + " |")
            out.append("\n".join(lines) + "\n")
            out.append(f"*{to_md(args[1])}*\n")
    Path(destino).write_text("\n".join(out), encoding="utf-8")


# ---------------------------------------------------------------- main

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    data, fits, der, _ = datos(Path(sys.argv[1]))
    h, r, it = tabla_wilson(data, fits, der)
    tablas = {"wilson": (h, r, it, [3.4, 1.6, 2.5, 1.8, 1.2, 2.2, 3.0])}
    h, r, it = tabla_st(data, der)
    tablas["st"] = (h, r, it, [3.0, 2.7, 2.7, 2.7, 1.8, 3.6])
    h, r, it = tabla_comparacion(data, fits, der)
    tablas["comparacion"] = (h, r, it, [6.0, 5.0, 5.5])
    bloques = [
        ("h1", "Informe BC: intercambiadores de calor. Resultados y discusión"),
        ("meta", "30 de septiembre de 2026 · Datos: v3009_v1.xlsx · Versión en castellano de "
                 "la sección 3 del borrador"),
        ("h2", "Notas para el equipo (borrar antes de entregar)"),
        *NOTAS,
        *contenido(data, fits, der),
    ]
    construir_docx(bloques, tablas, BASE / "discusion_resultados_BC.docx")
    construir_md(bloques, tablas, BASE / "discusion_resultados_BC.md")
    print("ok:", BASE / "discusion_resultados_BC.docx")


if __name__ == "__main__":
    main()
