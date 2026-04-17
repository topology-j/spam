import pandas as pd

df = pd.read_csv(r"C:\Users\green\Desktop\archive2\spam.csv", encoding="latin-1")
print(df.head())
print(df.columns)

df = df[['v1', 'v2']]
df.columns = ['label', 'text']

print(df.head())
print(df['label'].value_counts())

##X/Y나누기
X = df['text']
y = df['label']