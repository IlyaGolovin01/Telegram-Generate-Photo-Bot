from ai_logic import generate_image

prompt = input("Введите запрос: ")
generate_image(prompt, "result.png")
print("Сохранено в result.png")