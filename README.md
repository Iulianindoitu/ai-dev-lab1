# AI Classroom

Prototipul static al clasei AI, construit cu Python și pygame.

## Rulare

Instalează dependențele și pornește aplicația:

```powershell
python -m pip install -r requirements.txt
python main.py
```

Fereastra afișează tabla, cele șase bănci și eleve/elevi, profesorul și
clasamentul. Închide fereastra sau apasă `Esc` pentru a ieși. Bucla grafică
rulează la maximum 60 FPS. Istoricul rundelor este salvat în
`results/history.json`; locația poate fi schimbată prin
`AI_CLASSROOM_HISTORY_PATH`.

Providerul offline `mock` generează răspunsuri demonstrative adaptate
întrebării și personalității fiecărui elev; bula marchează aceste răspunsuri
cu eticheta `DEMO`. Rangul și timpul răspunsurilor sunt afișate în clasă și
salvate în istoricul rundelor. În timpul jocului, punctele de gândire,
mâinile ridicate, deplasarea profesorului și punctajele animate indică
activitatea clasei.

Dacă `GEMINI_API_KEY` este definit în `.env`, elevul Gemini folosește API-ul
Google Gemini; ceilalți elevi rămân pe providerul offline `mock`. La o eroare
Gemini sau la un răspuns gol, elevul Gemini primește un răspuns `mock` în loc.
Dependența `google-genai` este instalată împreună cu celelalte pachete din
`requirements.txt`.
