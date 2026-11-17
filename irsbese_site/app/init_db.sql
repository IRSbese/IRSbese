CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price >= 0),
    description TEXT NOT NULL,
    image TEXT NOT NULL DEFAULT ''
);

INSERT INTO products (id, name, category, price, description, image)
VALUES
    (1, 'Наушники беспроводные', 'Электроника', 3490,
     'Беспроводные наушники для повседневного использования.', ''),
    (2, 'Рюкзак городской', 'Аксессуары', 2190,
     'Удобный городской рюкзак.', ''),
    (3, 'Настольная лампа', 'Для дома', 1590,
     'Лаконичная лампа для рабочего стола.', ''),
    (4, 'Клавиатура', 'Электроника', 4290,
     'Клавиатура для работы и учёбы.', '');