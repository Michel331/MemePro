from django.shortcuts import render, redirect
from .models import Meme
from django.core.files.base import ContentFile
from django.conf import settings # Importe les configurations du projet, comme BASE_DIR.
from PIL import Image, ImageDraw, ImageFont # Importe les classes nécessaires de Pillow pour manipuler les images.
import io # Utilisé pour manipuler les flux de bytes en mémoire (comme une image générée).
import os # Fournit des fonctions pour interagir avec le système d'exploitation (ex: lister des fichiers).
from django.contrib import messages # Permet d'afficher des messages flash (notifications) à l'utilisateur.

# --- Fonctions Utilitaires --- #
# Ces fonctions aident à organiser le code et à éviter la répétition.
# Elles effectuent des tâches spécifiques et peuvent être réutilisées ailleurs si besoin.

def get_available_fonts():
    """
    Scanne le dossier 'fonts' à la racine du projet.
    Pourquoi scanner ce dossier ? Pour permettre à l'utilisateur de choisir parmi plusieurs polices.
    Retourne une liste de polices de caractères (.ttf ou .otf) qu'il contient.
    Chaque police est un dictionnaire avec:
        - 'file': le nom du fichier (ex: 'Arial.ttf'), nécessaire pour Pillow.
        - 'name': un nom lisible (ex: 'Arial'), pour l'affichage dans le sélecteur HTML.
    La liste est triée par nom lisible pour une meilleure expérience utilisateur.
    """
    # settings.BASE_DIR est le chemin absolu vers la racine du projet Django.
    # On construit le chemin vers le dossier 'fonts' qui doit être créé à cette racine.
    fonts_dir = os.path.join(settings.BASE_DIR, 'fonts')
    available_fonts = [] # Initialise une liste vide pour stocker les polices trouvées.

    # On vérifie d'abord si le dossier 'fonts' existe pour éviter une erreur.
    if os.path.exists(fonts_dir):
        # os.listdir() retourne la liste des fichiers et dossiers dans fonts_dir.
        for file_name in os.listdir(fonts_dir):
            # On ne s'intéresse qu'aux fichiers se terminant par .ttf ou .otf (formats de police courants).
            # .lower() est utilisé pour rendre la vérification insensible à la casse (ex: .TTF).
            if file_name.lower().endswith(('.ttf', '.otf')):
                # Création d'un nom lisible à partir du nom de fichier.
                # os.path.splitext(file_name)[0] enlève l'extension (ex: 'Cabilla' pour 'Cabilla.ttf').
                # .replace('-', ' ') et .replace('_', ' ') remplacent les tirets/underscores par des espaces.
                readable_name = os.path.splitext(file_name)[0].replace('-', ' ').replace('_', ' ')
                # .title() met la première lettre de chaque mot en majuscule (ex: 'open sans' -> 'Open Sans').
                available_fonts.append({
                    'file': file_name, # Le nom de fichier original.
                    'name': readable_name.title() # Le nom formaté pour l'affichage.
                })
    # Trie la liste des polices par leur nom lisible ('name') par ordre alphabétique.
    # La fonction lambda définit que le tri doit se baser sur la valeur de la clé 'name' de chaque dictionnaire.
    return sorted(available_fonts, key=lambda font: font['name'])

def _generate_image_with_text(image_path, top_text, bottom_text, font_file_name):
    """
    Prend le chemin d'une image, des textes (haut et bas) et un nom de fichier de police.
    Le but est de superposer ces textes sur l'image.
    Retourne une nouvelle image (en tant qu'objet ContentFile de Django) avec les textes incrustés.
    ContentFile est utile car il peut être directement sauvegardé dans un ImageField de Django.
    Si une erreur se produit pendant la génération, retourne None pour pouvoir la gérer dans la vue.
    Le préfixe '_' (par convention Python) indique que c'est une fonction "interne" ou "privée"
    à ce module (views.py), signifiant qu'elle n'est pas destinée à être importée et utilisée directement
    par d'autres modules, bien que Python ne l'interdise pas techniquement.
    """
    try:
        # Ouvre l'image à partir du chemin fourni.
        # .convert('RGB') est important pour s'assurer que l'image est dans un format de couleur standard (Rouge, Vert, Bleu)
        # que Pillow peut facilement traiter pour ajouter du texte et sauvegarder en JPEG.
        # Certaines images (comme les PNG avec transparence) pourraient causer des problèmes sinon.
        img = Image.open(image_path).convert('RGB')
        # Crée un objet Draw qui permet de dessiner sur l'image 'img'.
        draw = ImageDraw.Draw(img)

        # Chargement de la police.
        pil_font = None
        if font_file_name: # Si un nom de fichier de police a été fourni.
            try:
                # Construit le chemin complet vers le fichier de police.
                font_full_path = os.path.join(settings.BASE_DIR, 'fonts', font_file_name)
                # Tente de charger la police avec une taille de 60px.
                # La taille pourrait être rendue dynamique ou configurable à l'avenir.
                pil_font = ImageFont.truetype(font_full_path, size=60)
            except IOError: # Si le fichier de police n'est pas trouvé ou est corrompu.
                # Affiche un message dans la console du serveur (pour le débogage).
                print(f"Attention: Police '{font_file_name}' non trouvée ou illisible. Utilisation de la police par défaut.")
                # Charge une police par défaut de Pillow pour que l'application ne plante pas.
                pil_font = ImageFont.load_default()
        else: # Si aucun nom de fichier de police n'a été fourni (par exemple, si le dossier 'fonts' est vide).
            pil_font = ImageFont.load_default()

        # Récupère les dimensions de l'image pour calculer les positions du texte.
        img_width, img_height = img.size

        # Calcule les marges et positions pour le texte.
        # Ces valeurs sont relatives à la taille de l'image pour un meilleur ajustement.
        # text_margin_y: Marge en haut et en bas, 10% de la hauteur de l'image.
        line_spacing_factor = 0.1 # Facteur pour l'espacement vertical du texte.
        text_margin_y = int(img_height * line_spacing_factor)

        # Position Y pour le texte du haut : la marge.
        text_y_top = text_margin_y
        # Position Y pour le texte du bas.
        # On part du bas de l'image (img_height), on soustrait la marge,
        # et on soustrait la hauteur de la police (pil_font.getbbox('Ay')[3])
        # pour que le texte soit aligné par sa ligne de base. 'Ay' est utilisé pour obtenir une hauteur représentative.
        # L'index [3] de getbbox (tuple: left, top, right, bottom) donne la coordonnée 'bottom' par rapport à l'origine du texte.
        text_y_bottom = img_height - text_margin_y - pil_font.getbbox('Ay')[3]

        # Fonction interne pour dessiner le texte avec un contour.
        # Ceci est défini ici car elle utilise 'draw', 'pil_font', et 'img_width'.
        def draw_text_with_outline(text, y_position):
            # Centre le texte horizontalement. 'anchor="ms"' signifie que (x_position, y_position)
            # est le milieu du côté supérieur du texte ("middle-top" pour Pillow, 'm' pour x-axis, 's' pour y-axis baseline).
            x_position = img_width / 2
            outline_color = 'black' # Couleur du contour.
            text_color = 'white'    # Couleur du texte principal.

            # Dessine le contour en décalant légèrement le texte dans 4 directions.
            # C'est une technique simple pour simuler un contour.
            for offset in [(-2, -2), (2, -2), (-2, 2), (2, 2)]: # Décalages en pixels.
                draw.text(
                    (x_position + offset[0], y_position + offset[1]), # Position décalée.
                    text,
                    font=pil_font,
                    fill=outline_color, # Couleur du contour.
                    anchor='ms' # Ancre le texte au milieu horizontalement et sur sa ligne de base verticalement.
                )
            # Dessine le texte principal par-dessus le contour.
            draw.text((x_position, y_position), text, font=pil_font, fill=text_color, anchor='ms')

        # Ajoute le texte du haut s'il est fourni.
        # .upper() pour mettre le texte en majuscules, style classique des mèmes.
        if top_text:
            draw_text_with_outline(top_text.upper(), text_y_top)

        # Ajoute le texte du bas s'il est fourni.
        if bottom_text:
            draw_text_with_outline(bottom_text.upper(), text_y_bottom)

        # Sauvegarde de l'image générée en mémoire.
        # io.BytesIO() crée un "fichier" en mémoire vive.
        buffer = io.BytesIO()
        # Sauvegarde l'image 'img' dans le buffer au format JPEG.
        # Le format JPEG est courant pour les photos et bien supporté.
        img.save(buffer, format='JPEG')
        # buffer.seek(0) "rembobine" le curseur du buffer au début.
        # Nécessaire avant de lire son contenu, car .save() a laissé le curseur à la fin.
        buffer.seek(0)

        # Crée un ContentFile Django à partir du contenu du buffer.
        # ContentFile est un objet fichier que Django peut utiliser pour enregistrer dans un champ FileField/ImageField.
        # Le nom 'meme_generated.jpg' est un nom par défaut, il sera typiquement renommé lors de la sauvegarde dans le modèle.
        return ContentFile(buffer.read(), name=f"meme_generated.jpg")

    except Exception as e: # Gestion générique des erreurs.
        # Si quoi que ce soit échoue (ouverture image, chargement police, dessin, sauvegarde),
        # on affiche l'erreur dans la console du serveur et on retourne None.
        print(f"Erreur critique lors de la génération de l'image : {e}")
        return None

# --- Vues --- #
# Les vues sont des fonctions (ou classes) Python qui reçoivent une requête web
# et retournent une réponse web.

def meme_create(request):
    """
    Gère la création de mèmes.
    Si la requête est GET : affiche le formulaire de création vide (ou pré-rempli si erreur précédente).
    Si la requête est POST : traite les données soumises du formulaire pour créer un nouveau mème.
    """
    # Récupère la liste des polices disponibles pour le sélecteur dans le template.
    available_fonts = get_available_fonts()

    # Logique pour déterminer la police sélectionnée par défaut.
    # On essaie d'utiliser 'Cabilla.ttf' si elle existe.
    default_font_filename = 'Cabilla.ttf'
    if not any(font['file'] == default_font_filename for font in available_fonts) and available_fonts:
        # Si 'Cabilla.ttf' n'est pas là mais qu'il y a d'autres polices, on prend la première de la liste.
        default_font_filename = available_fonts[0]['file']
    elif not available_fonts:
        # S'il n'y a aucune police, on met None. _generate_image_with_text utilisera alors une police par défaut.
        default_font_filename = None

    # Le 'context' est un dictionnaire qui passe des données de la vue au template HTML.
    # Le template utilisera ces données pour s'afficher dynamiquement.
    context = {
        'fonts': available_fonts, # La liste des polices pour le <select>.
        'selected_font': default_font_filename, # La police qui doit être pré-sélectionnée.
        'top_text': '', # Valeur initiale pour le champ de texte du haut.
        'bottom_text': '' # Valeur initiale pour le champ de texte du bas.
    }

    # request.method indique le type de requête HTTP (GET, POST, etc.).
    if request.method == 'POST':
        # Le formulaire a été soumis, il faut traiter les données.
        # request.FILES contient les fichiers uploadés (ici, l'image originale).
        # .get('original_image') récupère le fichier associé au champ <input type="file" name="original_image">.
        original_image_file = request.FILES.get('original_image')
        # request.POST contient les données des champs de formulaire (textes, sélection).
        # .get('top_text', '') récupère la valeur du champ 'top_text'. Si non fourni, utilise une chaîne vide.
        # .strip() enlève les espaces en début et fin de chaîne (pour éviter des textes vides composés juste d'espaces).
        top_text = request.POST.get('top_text', '').strip()
        bottom_text = request.POST.get('bottom_text', '').strip()
        # Récupère la police sélectionnée par l'utilisateur.
        # Si non fournie dans le POST (ce qui ne devrait pas arriver si le <select> a une option),
        # on utilise la `default_font_filename` calculée plus haut.
        selected_font_filename = request.POST.get('font_selection', default_font_filename)

        # Met à jour le contexte avec les valeurs soumises.
        # Si la validation échoue et qu'on ré-affiche le formulaire,
        # les champs seront pré-remplis avec ce que l'utilisateur avait tapé.
        context['top_text'] = top_text
        context['bottom_text'] = bottom_text
        context['selected_font'] = selected_font_filename

        # --- Validations des données ---
        # Il est crucial de valider les données reçues du client.

        # 1. Vérifier si une image a été fournie.
        if not original_image_file:
            # messages.error() ajoute un message d'erreur qui sera affiché à l'utilisateur (via le template base.html).
            messages.error(request, "Veuillez sélectionner une image.")
            # Ré-affiche le formulaire de création avec le message d'erreur et les données déjà saisies.
            return render(request, 'meme/meme_create.html', context)

        # 2. Vérifier si au moins un des champs de texte est rempli.
        if not top_text and not bottom_text:
            messages.error(request, "Veuillez remplir au moins un champ de texte (haut ou bas).")
            return render(request, 'meme/meme_create.html', context)

        # --- Création de l'objet Mème et génération de l'image ---
        # Si les validations sont passées :

        # Crée une nouvelle instance du modèle `Meme` dans la base de données.
        # On sauvegarde d'abord l'image originale et les textes.
        # L'objet `meme_instance` contiendra l'ID généré par la base de données,
        # utile pour nommer l'image générée de manière unique.
        meme_instance = Meme.objects.create(
            original_image=original_image_file,
            top_text=top_text,
            bottom_text=bottom_text
            # Le champ 'generated_image' sera rempli après la génération.
        )

        # Appelle la fonction utilitaire pour générer l'image du mème.
        # On utilise meme_instance.original_image.path pour obtenir le chemin sur le serveur
        # de l'image originale qui vient d'être sauvegardée par Django.
        generated_image_content_file = _generate_image_with_text(
            image_path=meme_instance.original_image.path,
            top_text=top_text,
            bottom_text=bottom_text,
            font_file_name=selected_font_filename # La police choisie par l'utilisateur.
        )

        # Vérifie si la génération de l'image a réussi.
        if generated_image_content_file:
            # Si oui, sauvegarde l'image générée dans le champ 'generated_image' de l'instance Meme.
            # Le nom du fichier est construit dynamiquement pour inclure l'ID du mème, assurant son unicité.
            # save=True force la sauvegarde de l'instance Meme dans la base de données après cette modification.
            meme_instance.generated_image.save(f'meme_{meme_instance.id}.jpg', generated_image_content_file, save=True)
            messages.success(request, "Mème créé avec succès !") # Message de succès.
            # Redirige l'utilisateur vers la galerie pour voir son mème et les autres.
            # 'meme_gallery' est le nom de l'URL défini dans urls.py.
            return redirect('meme_gallery')
        else:
            # Si la génération a échoué (la fonction utilitaire a retourné None).
            # Il faudrait idéalement supprimer `meme_instance` ici car il est incomplet,
            # ou ajouter un statut pour indiquer l'échec de génération.
            # Pour l'instant, on affiche une erreur et on retourne au formulaire.
            # L'instance `Meme` sans image générée existera dans la base de données.
            messages.error(request, "Erreur lors de la génération de l'image du mème.")
            # Note: L'image originale et les textes sont déjà dans `context`
            return render(request, 'meme/meme_create.html', context)

    # Si la méthode n'est pas POST (c'est donc une requête GET initiale),
    # affiche simplement le formulaire de création vierge (ou avec des valeurs par défaut).
    return render(request, 'meme/meme_create.html', context)

def meme_gallery(request):
    """
    Affiche la galerie de tous les mèmes qui ont une image générée.
    """
    # Récupère tous les objets Meme de la base de données.
    # .exclude(generated_image__exact='') : Exclut les mèmes où le chemin de l'image générée est une chaîne vide.
    # .exclude(generated_image__isnull=True) : Exclut les mèmes où le champ de l'image générée est NULL (non défini).
    # Ces deux conditions assurent qu'on ne tente pas d'afficher des mèmes sans image finale.
    # .order_by('-created_at') : Trie les mèmes par date de création, du plus récent au plus ancien.
    # Le '-' avant 'created_at' indique un tri descendant.
    memes = Meme.objects.exclude(generated_image__exact='').exclude(generated_image__isnull=True).order_by('-created_at')
    # Passe la liste des mèmes au template 'meme_gallery.html' via le contexte.
    return render(request, 'meme/meme_gallery.html', {'memes': memes})

# Si vous vous demandez ce qu'est "request" :
# C'est un objet que Django crée automatiquement chaque fois qu'une page est demandée.
# Il contient des informations sur la requête entrante, comme l'utilisateur connecté (s'il y en a un),
# les données envoyées par un formulaire (request.POST), les fichiers uploadés (request.FILES),
# la méthode HTTP utilisée (GET, POST), etc. C'est un élément central dans la gestion des vues Django.

# Et "render" ?
# C'est une fonction raccourci de Django. Elle prend la requête, le nom d'un template HTML,
# et un dictionnaire de contexte. Elle "rend" (génère) le HTML en combinant le template
# avec les données du contexte, puis retourne une HttpResponse avec ce HTML.
# C'est la manière la plus courante de retourner du contenu HTML à l'utilisateur.
