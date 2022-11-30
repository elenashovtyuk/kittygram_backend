# импортируем модуль для кодирования или декодирования
import base64
# из модуля django.core.files.base импортируем класс ContentFile
# который работает со строковым содержимым, а не с реальным файлом
from django.core.files.base import ContentFile
# импортируем модуль для работы с сериализаторами
from rest_framework import serializers
# импортируем модуль для конвертирования кода цвета в его название и наоборот
import webcolors

# импортируем модуль для работы с датами
import datetime as dt
# импортируем нужные модели
from .models import Achievement, AchievementCat, Cat

# создаем новый тип поля, унаследованный от базового Field
# в нем два метода - для чтения и для записи
class Hex2NameColor(serializers.Field):
    # При чтении данных ничего не меняем - просто возвращаем как есть
    def to_representation(self, value):
        return value
    # При записи код цвета конвертируется в его название
    def to_internal_value(self, data):
        # проверяем
        # Если имя цвета существует, то конвертируем код в название
        try:
            data = webcolors.hex_to_name(data)
        # Иначе возвращаем ошибку
        except ValueError:
            raise serializers.ValidationError('Для этого цвета нет имени')
        # если же все ок, то возвращаем новый формат данных
        return data


class AchievementSerializer(serializers.ModelSerializer):
    achievement_name = serializers.CharField(source='name')

    class Meta:
        model = Achievement
        fields = ('id', 'achievement_name')

# создаем кастомный тип поля, унаследованный от ImageField
class Base64ImageField(serializers.ImageField):
    # в нем переопределяем метод 'to_internal_value' -
    # для того, чтобы изменить поведение сериализации/десериализации
    def to_internal_value(self, data):
        # Если полученный объект строка, и эта строка
        # начинается с 'data:image'(что говорит о характере данных)
        if isinstance(data, str) and data.startswith('data:image'):
            # ...начинаем декодировать изображение из base64.
            # Сначала нужно разделить строку на части.
            # в качестве разделителя используем выражение ';base64,'
            # в итоге получаем 2 части:
            # format - это спецификацию типа, формат данных
            # и imgstr - это закодированное содержимое файла
            format, imgstr = data.split(';base64,')
            # из первой части, полученной при делении далее извлекаем расширение файла
            ext = format.split('/')[-1]
            # Затем декодируем сами данные из второй части полученной при делении
            # и помещаем результат в файл,
            # которому даем название по шаблону.
            # для этого используем класс ContentFile,где
            # первым параметром указываем функцию декодирования из модуля base64
            # декодируем imgstr - закодированное содержимое файла
            # вторым парамметром указываем имя файлу, которому даем название по шаблону + расширение
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)

        return super().to_internal_value(data)

# в сериализаторе для модели Cat для полей color и image
# задем новые кастомнеы типы полей, которые создали выше
class CatSerializer(serializers.ModelSerializer):
    achievements = AchievementSerializer(required=False, many=True)
    color = Hex2NameColor()
    age = serializers.SerializerMethodField()
    image = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = Cat
        fields = (
            'id',
            'name',
            'color',
            'birth_year',
            'achievements',
            'owner',
            'age',
            'image'
            )
        read_only_fields = ('owner',)

    def get_age(self, obj):
        return dt.datetime.now().year - obj.birth_year

    def create(self, validated_data):
        if 'achievements' not in self.initial_data:
            cat = Cat.objects.create(**validated_data)
            return cat
        else:
            achievements = validated_data.pop('achievements')
            cat = Cat.objects.create(**validated_data)
            for achievement in achievements:
                current_achievement, status = Achievement.objects.get_or_create(
                    **achievement
                    )
                AchievementCat.objects.create(
                    achievement=current_achievement, cat=cat
                    )
            return cat
    # В сериализатор также был добавлен метод update,
    # который отвечает за обновление данных о котиках:
    # то есть, добавляем возможность изменять уже существующие записи
    # в этот метод передаем ссылку на объект instance (объект модели Cat), который нужно изменить
    # и validated_data - словарь с проверенными данными
    def update(self, instance, validated_data):
        # воспользовавшись django ORM указываем instance.name,
        # потому что знаем, что у объекта модели Cat есть поле name
        # и присваиваем  ему значение из коллекции (словаря) validated_data
        # обратившись по нужному ключу (name соответственно) и если
        # по какой-то причине этот ключ не был найден в словаре, то
        # вернем тот name, который уже есть в модели Cat
        instance.name = validated_data.get('name', instance.name)
        # аналогично со всеми остальными значениями полей, которые нужно изменить
        # для поля color
        instance.color = validated_data.get('color', instance.color)
        # для поля birth_year
        instance.birth_year = validated_data.get(
            'birth_year', instance.birth_year
            )
        # для поля image
        instance.image = validated_data.get('image', instance.image)
        # для поля с достижениями котиков делаем следующую проверку:
        # если в словаре с проверенными данными есть достижения(ключ 'achievements')
        if 'achievements' in validated_data:
            # то мы удаляем эти достижения из словаря с проверенными данными
            #  и сохраняем их в переменную achievements_data
            achievements_data = validated_data.pop('achievements')
            # создаем пустой список
            lst = []
            # для каждого достижения в списке достижений
            for achievement in achievements_data:
                # создаем новую или получаем уже существующую запись достижения
                current_achievement, status = Achievement.objects.get_or_create(
                    **achievement
                    )
                # добавялем запись достижения в пустой список созданный ранее
                lst.append(current_achievement)
            # полученный список достижений преобразуем в множество
            # (то есть, уникальную коллекцию достижений)
            instance.achievements.set(lst)
        # в конце мы вызываем метод save, чтобы сохранить все измененные данные
        instance.save()
        # и возвращаем полученный результат
        return instance
