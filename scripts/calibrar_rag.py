"""Ayuda para elegir RAG_UMBRAL (similitud minima del RAG).

Uso:  python -m scripts.calibrar_rag

Muestra la mejor similitud de preguntas que SI estan en los PDFs y de preguntas
que NO. El umbral ideal separa ambos grupos: mas bajo que las primeras y mas alto
que las segundas. Copiar el valor sugerido al .env como RAG_UMBRAL=...
"""
from src.rag.retriever import buscar

SI_ESTAN = [
    "¿Cuál es el plazo para devolver un producto?",
    "How many days do I have to return a product?",
    "¿Cuánta garantía tienen las notebooks?",
    "What is the warranty on storage drives?",
    "¿Cómo se hace el reembolso si pagué con tarjeta de crédito?",
    "¿Qué incluye la caja de la cámara web 4K?",
    "What are the specifications of the Aurora Book 14?",
    "¿Qué no cubre la garantía?",
]
NO_ESTAN = [
    "¿Quién ganó el Mundial de fútbol 2022?",
    "What is the capital of Australia?",
    "Receta de milanesas con puré",
    "¿Cuál es la mejor película de 2019?",
    "How do I train for a marathon?",
]


def mejor(pregunta):
    r = buscar(pregunta, k=1, umbral=-1.0)
    return r[0].similitud if r else 0.0


def main():
    print("Preguntas que SI estan en los documentos:")
    si = [(mejor(q), q) for q in SI_ESTAN]
    for s, q in si:
        print(f"  {s:.3f}  {q}")
    print("\nPreguntas que NO estan:")
    no = [(mejor(q), q) for q in NO_ESTAN]
    for s, q in no:
        print(f"  {s:.3f}  {q}")
    minimo_si = min(s for s, _ in si)
    maximo_no = max(s for s, _ in no)
    print(f"\nMenor similitud entre las que SI estan: {minimo_si:.3f}")
    print(f"Mayor similitud entre las que NO estan: {maximo_no:.3f}")
    if minimo_si > maximo_no:
        print(f"Umbral sugerido: {(minimo_si + maximo_no) / 2:.2f}   (RAG_UMBRAL en el .env)")
    else:
        print("Los grupos se superponen: no hay un umbral perfecto. Elegir uno que descarte "
              "las que NO estan y aceptar que alguna que SI esta quede afuera.")


if __name__ == "__main__":
    main()
