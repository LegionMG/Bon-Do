#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode, ChatAction, ChatMember, Chat
from telegram.error import BadRequest
from tinydb import TinyDB, Query
from tinydb_serialization import SerializationMiddleware, Serializer
from datetime import date
from locales import Conf
import telegram.constants as constants
import random, re, time, datetime, operator, logging, os

LANGUAGE = 'ru'
RANTS_ONE = Conf.loc[LANGUAGE]["rants"]["one"]
RANTS_TWO = Conf.loc[LANGUAGE]["rants"]["two"]
BAD_STAT = {ChatMember.LEFT, ChatMember.KICKED, ChatMember.RESTRICTED}

class DateSerializer(Serializer):
    OBJ_CLASS = date

    def encode(self, obj):
        return obj.strftime('%Y-%m-%d')

    def decode(self, s):
        return datetime.datetime.strptime(s, '%Y-%m-%d').date()


TOKEN = os.environ['BONDOBOT_TOKEN']

updater = Updater(TOKEN)
dispatcher = updater.dispatcher
pattern = re.compile(r'\b[oо]+[xх]+\b', flags=re.IGNORECASE)
logging.basicConfig(filename='log.txt',
                    filemode='a',
                    format='%(message)s',
                    level=logging.ERROR)
serialization = SerializationMiddleware()
serialization.register_serializer(DateSerializer(), 'TinyDate')
db = TinyDB('db.json', storage=serialization)


def start(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text=Conf.loc[LANGUAGE]["start"])


def check_for_ohs_and_pidors(bot, update):
    reply_to_oh(bot=bot, update=update)
    chat_type = update.message.chat.type
    if chat_type == Chat.GROUP or chat_type == Chat.SUPERGROUP:
        save_pidor(bot=bot, update=update)


def save_pidor(bot, update):
    Pidor = Query()
    user_id = update.message.from_user.id
    chat_id = update.message.chat.id
    if not db.contains((Pidor.user_id == user_id) & (Pidor.chat_id == chat_id)):
        db.insert({'user_id': user_id, 'chat_id': chat_id, 'won': 0})


def reply_to_oh(bot, update):
    this_message = update.message
    text = this_message.text

    if pattern.search(text):
        bot.send_message(update.message.chat.id, random.randint(1, 8) * 'о' + random.randint(1, 8) * 'х' + random.randint(0, 3) * '.')


def pidor(bot, update):
    chat_id = update.message.chat.id
    today = datetime.date.today()
    PidorDate = Query()
    saved_pidor = db.get((PidorDate.date.exists()) & (PidorDate.chat_id == chat_id))
    if not saved_pidor:
        saved_pidor = {'date': date(1970, 1, 1), 'chat_id': chat_id, 'user_id': 0}
    saved = saved_pidor['date']
    text = ''
    pidor_user = None

    if today > saved:
        pidor_of_the_day = None
        Pidor = Query()
        pidors = db.search((Pidor.won.exists()) & (Pidor.chat_id == chat_id))
        while not pidor_of_the_day:
            pidors_length = len(pidors)
            if pidors_length == 0:
                bot.send_message(chat_id=chat_id, text=Conf.loc[LANGUAGE]["not_found"])
                return
            index = random.randint(0, pidors_length-1)
            pidor_of_the_day = pidors[index]
            pidor_user = get_pidor_user(bot=bot, chat_id=chat_id, user_id=pidor_of_the_day['user_id'])
            if not pidor_user:
                return  
            if pidor_user.status in BAD_STAT:
                pidor_user = pidor_user.user
                bot.send_message(chat_id=chat_id, text=Conf.loc[LANGUAGE]["bad_status"].format(user=pidor_user.mention_html(pidor_user.full_name)),
                        parse_mode=ParseMode.HTML)
                bot.send_message(chat_id=chat_id, text=Conf.loc[LANGUAGE]["try_again"])
                db.remove((Pidor.won.exists()) & (Pidor.chat_id == chat_id) & (Pidor.user_id == pidor_user.id))
                del pidors[index]
                pidor_of_the_day = None
            else:
                pidor_of_the_day['won'] += 1
                db.upsert(pidor_of_the_day, (Pidor.won.exists()) & (Pidor.chat_id == chat_id) & (Pidor.user_id == pidor_of_the_day['user_id']))
                saved_pidor['user_id'] = pidor_of_the_day['user_id']
                saved_pidor['date'] = today
                db.upsert(saved_pidor, (Pidor.date.exists()) & (Pidor.chat_id == chat_id))
                text = Conf.loc[LANGUAGE]["found"]
                bot.send_message(chat_id=chat_id, text=Conf.loc[LANGUAGE]["search"])
                time.sleep(1.5)
                bot.send_message(chat_id=chat_id, text=random.choice(RANTS_ONE))
                time.sleep(1.5)
                bot.send_message(chat_id=chat_id, text=random.choice(RANTS_TWO), parse_mode=ParseMode.MARKDOWN)
                time.sleep(1.5)
    else:
        pidor_user = get_pidor_user(bot=bot, chat_id=chat_id, user_id=saved_pidor['user_id'])
        if not pidor_user:
            return
        text = Conf.loc[LANGUAGE]["already_found"]
    pidor_user = pidor_user.user
    bot.send_message(chat_id=chat_id, text=text + pidor_user.mention_html(pidor_user.full_name), parse_mode=ParseMode.HTML)


def get_pidor_user(bot, chat_id, user_id):
    try:
        return bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except BadRequest:
        bot.send_message(chat_id=chat_id, text=Conf.loc[LANGUAGE]["error_by"].format(user=user_id))
        return None


def pidor_stats(bot, update):
    chat_id = update.message.chat.id
    message = None
    Pidor = Query()
    pidors = db.search((Pidor.won.exists()) & (Pidor.chat_id == chat_id))
    if len(pidors) == 0:
        message = Conf.loc[LANGUAGE]["empty_list"]
    else:
        message = Conf.loc[LANGUAGE]["top"]
        sorted_pidors = sorted(pidors, key=operator.itemgetter('won'), reverse=True)
        for pidor in sorted_pidors:
            if pidor['won'] == 0:
                continue
            pidor_user = get_pidor_user(bot=bot, chat_id=chat_id, user_id=pidor['user_id'])
            if not pidor_user:
                continue
            name = pidor_user.user.full_name
            message += '_' + name + '_: ' + str(pidor['won']) + '\n'
    bot.send_message(chat_id, text=message, parse_mode=ParseMode.MARKDOWN)


start_handler = CommandHandler(str('start'), start)
pidor_handler = CommandHandler(str('pidor'), pidor, Filters.group)
pidor_stats_handler = CommandHandler(str('pidorstats'), pidor_stats, Filters.group)
oh_handler = MessageHandler(Filters.text, check_for_ohs_and_pidors)

dispatcher.add_handler(start_handler)
dispatcher.add_handler(pidor_handler)
dispatcher.add_handler(pidor_stats_handler)
dispatcher.add_handler(oh_handler)
updater.start_polling()
updater.idle()
