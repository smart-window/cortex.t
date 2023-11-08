import sys
sys.path.insert(0, '/root/bittensor/bittensor')

import bittensor as bt
from dendrite import * 
import os
import time
import torch
import argparse
import traceback
import template
import openai
import wandb
import re
import random
import ast
import asyncio
import logging

openai.api_key = os.environ.get('OPENAI_API_KEY')
if not openai.api_key:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

theme_counter = 0
question_counter = 0
themes = None
questions_list = None

def get_config():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alpha", default=0.9, type=float)
    parser.add_argument("--custom", default="my_custom_value")
    parser.add_argument("--netuid", type=int, default=1)
    parser.add_argument( '--wandb.on', action='store_true', help='Turn on wandb logging.')
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    bt.wallet.add_args(parser)
    config = bt.config(parser)
    config.full_path = os.path.expanduser(f"{config.logging.logging_dir}/{config.wallet.name}/{config.wallet.hotkey}/netuid{config.netuid}/validator")
    if not os.path.exists(config.full_path):
        os.makedirs(config.full_path, exist_ok=True)
    if config.wandb.on:
        run_name = f'validator-{my_uid}-' + ''.join(random.choice( string.ascii_uppercase + string.digits ) for i in range(10))
        config.uid = my_uid
        config.hotkey = wallet.hotkey.ss58_address
        config.run_name = run_name
        wandb_run =  wandb.init(
            name = run_name,
            anonymous = "allow",
            reinit = False,
            project = 'opentext_qa',
            entity = 'opentensor-dev',
            config = config,
            dir = config.full_path,
        )
        bt.logging.success( f'Started wandb run' )
    return config

def initialize_components(config):
    bt.logging(config=config, logging_dir=config.full_path)
    bt.logging.info(f"Running validator for subnet: {config.netuid} on network: {config.subtensor.chain_endpoint}")
    wallet = bt.wallet(config=config)
    subtensor = bt.subtensor(config=config)
    dendrite = bt.dendrite(wallet=wallet)
    metagraph = subtensor.metagraph(config.netuid)
    return wallet, subtensor, dendrite, metagraph

def check_validator_registration(wallet, subtensor, metagraph):
    if wallet.hotkey.ss58_address not in metagraph.hotkeys:
        bt.logging.error(f"Your validator: {wallet} is not registered to chain connection: {subtensor}. Run btcli register and try again.")
        exit()

def call_openai(prompt, temperature, engine="gpt-3.5-turbo"):
    try:
        messages = [{"role": "user", "content": prompt}]
        response = openai.ChatCompletion.create(
            model=engine,
            messages=messages,
            temperature=0,
        )
        answer = response["choices"][0]["message"]["content"].strip()
        return answer
    except Exception as e:
        bt.logging.info(f"Error when calling OpenAI: {e}")
        return None

def get_openai_answer(query, engine):
    temperature = 0
    answer = call_openai(query, temperature, engine)
    bt.logging.info(f"Response from validator openai: {answer}")
    return answer

def extract_python_list(text):
    try:
        # Find the first open bracket and the last closing bracket
        start_idx = text.find('[')
        end_idx = text.rfind(']')

        if start_idx == -1 or end_idx == -1:
            return None

        list_str = text[start_idx:end_idx+1]
        evaluated = ast.literal_eval(list_str)

        if isinstance(evaluated, list):
            return evaluated
        return None
    except Exception as e:
        bt.logging.info(text)
        bt.logging.error(f"Error when extracting list: {e}")
        return None

def get_list_from_openai(prompt, default_list, max_retries=5):
    for retry_count in range(max_retries):
        try:
            answer = call_openai(prompt, .33).replace("\n", " ")
            extracted_list = extract_python_list(answer)
            if extracted_list:
                return extracted_list
            else:
                bt.logging.info(f"No valid python list found, retry count: {retry_count + 1}")
        except Exception as e:
            bt.logging.error(f"Got exception when calling openai {e}")
    else:
        bt.logging.error(f"No list found after {max_retries} retries, using default list.")
        return default_list

def get_themes(num_themes=50):
    default_themes = ['Love and relationships', 'Nature and environment', 'Art and creativity', 'Technology and innovation', 'Health and wellness', 'History and culture', 'Science and discovery', 'Philosophy and ethics', 'Education and learning', 'Music and rhythm', 'Sports and athleticism', 'Food and nutrition', 'Travel and adventure', 'Fashion and style', 'Books and literature', 'Movies and entertainment', 'Politics and governance', 'Business and entrepreneurship', 'Mind and consciousness', 'Family and parenting', 'Social media and networking', 'Religion and spirituality', 'Money and finance', 'Language and communication', 'Human behavior and psychology', 'Space and astronomy', 'Climate change and sustainability', 'Dreams and aspirations', 'Equality and social justice', 'Gaming and virtual reality', 'Artificial intelligence and robotics', 'Creativity and imagination', 'Emotions and feelings', 'Healthcare and medicine', 'Sportsmanship and teamwork', 'Cuisine and gastronomy', 'Historical events and figures', 'Scientific advancements', 'Ethical dilemmas and decision making', 'Learning and growth', 'Music genres and artists', 'Film genres and directors', 'Government policies and laws', 'Startups and innovation', 'Consciousness and perception', 'Parenting styles and techniques', 'Online communities and forums', 'Religious practices and rituals', 'Personal finance and budgeting', 'Linguistic diversity and evolution', 'Human cognition and memory', 'Astrology and horoscopes', 'Environmental conservation', 'Personal development and self-improvement', 'Sports strategies and tactics', 'Culinary traditions and customs', 'Ancient civilizations and empires', 'Medical breakthroughs and treatments', 'Moral values and principles', 'Critical thinking and problem solving', 'Musical instruments and techniques', 'Film production and cinematography', 'International relations and diplomacy', 'Corporate culture and work-life balance', 'Neuroscience and brain function', 'Childhood development and milestones', 'Online privacy and cybersecurity', 'Religious tolerance and understanding', 'Investment strategies and tips', 'Language acquisition and fluency', 'Social influence and conformity', 'Space exploration and colonization', 'Sustainable living and eco-friendly practices', 'Self-reflection and introspection', 'Sports psychology and mental training', 'Globalization and cultural exchange', 'Political ideologies and systems', 'Entrepreneurial mindset and success', 'Conscious living and mindfulness', 'Positive psychology and happiness', 'Music therapy and healing', 'Film analysis and interpretation', 'Human rights and advocacy', 'Financial literacy and money management', 'Multilingualism and translation', 'Social media impact on society', 'Religious extremism and radicalization', 'Real estate investment and trends', 'Language preservation and revitalization', 'Social inequality and discrimination', 'Climate change mitigation strategies', 'Self-care and well-being', 'Sports injuries and rehabilitation', 'Artificial intelligence ethics', 'Creativity in problem solving', 'Emotional intelligence and empathy', 'Healthcare access and affordability', 'Sports analytics and data science', 'Cultural appropriation and appreciation', 'Ethical implications of technology']
    prompt = f"Give me a python list of {num_themes} different creative themes of which one could ask meaningful questions. Max four words each. Provide it in python list structure and don't write anything extra, just provide exclusively the complete list."
    themes = get_list_from_openai(prompt, default_themes)
    bt.logging.info(f"using themes of {themes}")
    return themes

def get_questions_list(theme):
    default_questions = ['What is the most important quality you look for in a partner?', 'How do you define love?', 'What is the most romantic gesture you have ever received?', 'What is your favorite love song and why?', 'What is the key to a successful long-term relationship?', 'What is your idea of a perfect date?', 'What is the best piece of relationship advice you have ever received?', 'What is the most memorable love story you have heard?', 'What is the biggest challenge in maintaining a healthy relationship?', 'What is your favorite way to show someone you love them?']
    prompt = f"Give me a python list of 10 different creative questions based off of the theme of {theme}. Max 15 words each. Provide it in python list structure and don't write anything extra, just provide exclusively the complete python list."
    questions = get_list_from_openai(prompt, [])
    return questions

def get_question():
    global theme_counter, question_counter, themes, questions_list

    if not themes:
        themes = get_themes()
        theme_counter = len(themes) - 1  # Start at the end of the themes list

    theme = themes[theme_counter]

    if not questions_list:
        questions_list = get_questions_list(theme)
        question_counter = len(questions_list) - 1  # Start at the end of the questions list
        bt.logging.info(f"retrieved new questions: {questions_list}")

    question = questions_list[question_counter]

    # Move backwards in the questions list
    question_counter -= 1
    if question_counter < 0:  # If we reach the front, get new questions
        questions_list = None
        theme_counter -= 1  # Move to the previous theme

        if theme_counter < 0:  # If we reach the front of themes, start over
            themes = None

    return question


def set_weights(step, scores, config, subtensor, wallet, metagraph):
    weights = torch.nn.functional.normalize(scores, p=1.0, dim=0)
    bt.logging.info(f"weights is {weights}")

    result = subtensor.set_weights(netuid=config.netuid, wallet=wallet, uids=metagraph.uids, weights=weights, wait_for_inclusion=True)
    if result:
        bt.logging.success("Successfully set weights.")
    else:
        bt.logging.error("Failed to set weights.")

def log_wandb(query, engine, responses_dict, step, timestamp):
    data = {
        '_timestamp': timestamp,
        '_runtime': time.time() - timestamp,
        'engine': engine,
        'prompt': query,
        '_step': step,
        'responses': []
    }

    for uid, response_data in responses_dict.items():
        response_entry = {
            'uid': uid,
            'response': response_data.get('response', None),
            'score': response_data.get('score', 0)
        }
        data['responses'].append(response_entry)

    wandb.log(data)

async def score_responses(synapse, config, openai_answer, full_response):
    try:
        score = template.reward.openai_score(openai_answer, full_response)
        response_dict = {}
        responses_dict['response'] = full_response
        responses_dict['score'] = score
        # scores = config.alpha * scores + (1 - config.alpha) * score

    except Exception as e:
        bt.logging.error(f"Error while scoring: {traceback.format_exc()}")

    return responses_dict

async def run_validator_loop(wallet, subtensor, dendrite, metagraph, config, scores):
    step = 0
    while True:
        try:
            bt.logging.info(f"Starting validator loop iteration {step}.")
            query = get_question()
            probability = random.random()
            engine = "gpt-4" if probability < 0.05 else "gpt-3.5-turbo"            
            bt.logging.info(f"Sent query to miner: '{query}' using {engine}")
            synapse = template.protocol.StreamPrompting(messages=[query], engine=engine)
            bt.logging.debug(f"synapse: {synapse}")
            responses = await dendrite(metagraph.axons, synapse, deserialize=False, streaming=True)

            async for resp in responses:
                i = 0
                async for chunk in resp:
                    i += 1
                    if i % 2 == 0:
                        bt.logging.info(chunk)
                    if isinstance(chunk, list):
                        print(chunk[0], end="", flush=True)
                    else:
                        synapse = chunk
                break
            
            # Now that the streaming is done, process the response
            openai_answer = get_openai_answer(query, engine)
            if openai_answer:
                for res in responses:
                    responses_dict = await score_responses(synapse, config, openai_answer, resp)
            
            bt.logging.info(f"responses_dict is {responses_dict}")
            if config.wandb.on: log_wandb(query, engine, responses_dict, step, time.time())

            if (step + 1) % 25 == 0:  
                set_weights(step, scores, config, subtensor, wallet, metagraph)

            bt.logging.info(f"step = {step}")
            step += 1
            metagraph = subtensor.metagraph(config.netuid)
            await asyncio.sleep(bt.__blocktime__ - 4)

        except RuntimeError as e:
            bt.logging.error(f"RuntimeError at step {step}: {e}")
        except Exception as e:
            bt.logging.info(f"General exception at step {step}: {e}\n{traceback.format_exc()}")
        except KeyboardInterrupt:
            bt.logging.success("Keyboard interrupt detected. Exiting validator.")
            if config.wandb.on: wandb_run.finish()
            exit()

def main(config):
    wallet, subtensor, dendrite, metagraph = initialize_components(config)
    check_validator_registration(wallet, subtensor, metagraph)
    my_subnet_uid = metagraph.hotkeys.index(wallet.hotkey.ss58_address)
    scores = torch.zeros_like(metagraph.S, dtype=torch.float32)
    
    asyncio.run(run_validator_loop(wallet, subtensor, dendrite, metagraph, config, scores))

if __name__ == "__main__":
    main(get_config())