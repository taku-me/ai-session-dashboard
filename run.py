import uvicorn
import os

def main():
    print("Starting AI Session Dashboard...")
    print("Local URL: http://localhost:8888")
    uvicorn.run("server:app", host="0.0.0.0", port=8888, reload=False)

if __name__ == "__main__":
    main()
