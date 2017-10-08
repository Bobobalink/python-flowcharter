from math import cos

n = int(input("memes: "))
n = 1 / n * 3 - 2
if n > 5 and n < 10 and n != 7 or n == 12:
    b = 2 * cos(n - 2) + 1
else:
    b = 2 * cos(n) + 1
    if 1 < n / 2 < 4:
        while b > 0:
            print(n - b)
            b -= 1
print(b)
