"ollama serve" in cmd

cd chatBotMicroservice

uvicorn main:app --reload --port 8000

cd investiqdemo

npm run dev

Summary of events:

There should be three separate terminal windows, one for each. Ollama on its default port 11434, FastAPI on 8000, Next.js on 3000.
