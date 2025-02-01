import sys

def generate_video(prompt):
    # Simulate generating the URL based on the prompt
    # Replace this logic with the actual implementation
    url = f"https://example.com/video?prompt={prompt.replace(' ', '+')}"
    return url

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: No prompt provided.")
        sys.exit(1)
    
    prompt = sys.argv[1]
    url = generate_video(prompt)
    print(url)
