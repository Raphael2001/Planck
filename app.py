from datetime import datetime
import json
import os
import pymongo
from flask import Flask
from flask_cors import CORS
from flask_restful import Resource, Api, reqparse, abort
import requests
import dns
import pytz

base = "https://www.10bis.co.il/NextApi/GetRestaurantMenu?culture=en&uiCulture=en&restaurantId=19156&deliveryMethod" \
       "=pickup "
app = Flask(__name__)
api = Api(app)
CORS(app)

app.config['CORS_HEADERS'] = 'Content-Type; utf-8'
app.config['Access-Control-Allow-Origin'] = '*'
client = pymongo.MongoClient(
    "mongodb+srv://Raphael:raph2001@bneibrakdelivery.w4awq.mongodb.net/myFirstDatabase?retryWrites=true&w=majority")
db = client.Planck
drinks_ref = db.Drinks
desserts_ref = db.Desserts
pizzas_ref = db.Pizzas
tracker = db.Tracker
last_ref_query = {'name': 'LastUpdated'}
tz_IL = pytz.timezone('Israel')


def get_tracking_by_query(query):
    # gets the tracking by query
    doc = tracker.find_one(query)
    if doc is not None:
        return doc["date"]

    else:
        abort(400, message=u'לא נמצא תאריך')


def update_all_dishes_in_database():
    update_category_in_database("Drinks", drinks_ref)
    update_category_in_database("Desserts", desserts_ref)
    update_category_in_database("Pizzas", pizzas_ref)


def update_category_in_database(category_name, ref):
    dishes = get_dish_list_by_category_name(category_name)
    for dish in dishes:
        ref.update_one({f"id": dish["dishId"]}, {"$set": {
            "id": dish["dishId"],
            "name": dish["dishName"],
            "description": dish["dishDescription"],
            "price": int(dish["dishPrice"]),

        }})


def get_dish_list_by_category_name(name):
    # returns a dish list by the name of the category
    response = requests.get(base)
    response = json.loads(response.content)
    data = response["Data"]
    categories = data["categoriesList"]
    for category in categories:
        if category["categoryName"] == name:
            return category["dishList"]


def get_total_dishes_by_category(dishes_to_cal, ref):
    # get the total sum of prices of dishes by ref
    total = 0
    for dish_id in dishes_to_cal:
        dish = find_id_in_ref(dish_id, ref)
        total += dish["price"]
    return total


def get_current_date():
    now = datetime.now(tz_IL)
    return now.strftime('%Y-%m-%d')


def does_need_update():
    date = get_tracking_by_query(last_ref_query)
    today = get_current_date()
    return today != date


def update_if_needed():
    if does_need_update():
        update_all_dishes_in_database()
        today = get_current_date()
        tracker.update_one(last_ref_query, {"$set": {
            "date": today,
        }})


def find_id_in_ref(id, ref):
    dish = ref.find_one({"id": id}, {'_id': 0})
    if dish is None:
        abort(400, message="לא נמצאה אף מנה עם מספר מזהה זה")
    return dish


def find_all_in_ref(ref):
    docs = ref.find({}, {'_id': 0})
    dishes = []
    for dish in docs:
        dishes.append(dish)
    return dishes


class Dishes(Resource):
    def __init__(self, **kwargs):
        self.ref = kwargs['ref']

    def get(self):
        update_if_needed()
        dishes = find_all_in_ref(self.ref)
        return {
            'statuscode': 200,
            'body': dishes,
            'message': "",
        }


class Dish(Resource):
    def __init__(self, **kwargs):
        self.ref = kwargs['ref']

    def get(self, id):
        update_if_needed()
        dish = find_id_in_ref(id, self.ref),
        return {
            'statuscode': 200,
            'body': dish,
            'message': "",
        }


class Order(Resource):
    def post(self):
        # gets the total sum of all the dishes
        parser = reqparse.RequestParser()  # initialize
        parser.add_argument("drinks", type=list, required=True, location='json', help="drinks is missing")
        parser.add_argument('desserts', type=list, required=True, location='json', help="desserts is missing")
        parser.add_argument('pizzas', type=list, required=True, location='json', help="pizzas is missing")
        args = parser.parse_args()
        total = 0
        update_if_needed()

        drinks = args["drinks"]
        desserts = args["desserts"]
        pizzas = args["pizzas"]

        total += get_total_dishes_by_category(drinks, drinks_ref)
        total += get_total_dishes_by_category(pizzas, pizzas_ref)
        total += get_total_dishes_by_category(desserts, desserts_ref)

        return {
            'statuscode': 200,
            'body': {"price": total},
            'message': "",
        }


api.add_resource(Dishes, '/api/v1/drinks', endpoint='drinks', resource_class_kwargs={'ref': drinks_ref})
api.add_resource(Dishes, '/api/v1/desserts', endpoint='desserts', resource_class_kwargs={'ref': desserts_ref})
api.add_resource(Dishes, '/api/v1/pizzas', endpoint='pizzas', resource_class_kwargs={'ref': pizzas_ref})
api.add_resource(Dish,'/api/v1/drink/<int:id>', endpoint='drink', resource_class_kwargs={'ref': drinks_ref})
api.add_resource(Dish, '/api/v1/pizza/<int:id>', endpoint='pizza', resource_class_kwargs={'ref': pizzas_ref})
api.add_resource(Dish, '/api/v1/dessert/<int:id>', endpoint='dessert', resource_class_kwargs={'ref': desserts_ref})
api.add_resource(Order, '/api/v1/order')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
