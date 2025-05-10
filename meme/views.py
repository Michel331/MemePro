from django.shortcuts import render, redirect
from .models import Meme
from django.core.files.base import ContentFile
from django.conf import settings # Configuration projet.
from PIL import Image, ImageDraw, ImageFont # Pillow pour images.
import io # Gestion bytes en mémoire (image générée).
import os # Interaction système (lister fichiers).
from django.contrib import messages # Notifications utilisateur.

# --- Mes Fonctions Utilitaires --- #
# Organisation et réutilisabilité.
# Fonctions pour tâches spécifiques.

def get_available_fonts():
    """
    Je scanne 'fonts/' pour lister les polices (.ttf, .otf).
    Permet à l'utilisateur de choisir sa police.
    Retourne liste de dictionnaires: {'file': 'NomFichier.ttf', 'name': 'Nom Lisible'}, triée.
    """
    # Chemin vers mon dossier 'fonts'.
    fonts_dir = os.path.join(settings.BASE_DIR, 'fonts')
    available_fonts = [] # Liste des polices trouvées.

    # Je vérifie l'existence du dossier 'fonts'.
    if os.path.exists(fonts_dir):
        # Je parcours les fichiers du dossier.
        for file_name in os.listdir(fonts_dir):
            # Je filtre par extension .ttf ou .otf.
            if file_name.lower().endswith(('.ttf', '.otf')):
                # Je génère un nom lisible.
                readable_name = os.path.splitext(file_name)[0].replace('-', ' ').replace('_', ' ')
                available_fonts.append({
                    'file': file_name, # Nom de fichier original.
                    'name': readable_name.title() # Nom formaté pour affichage.
                })
    # Je trie par nom.
    return sorted(available_fonts, key=lambda font: font['name'])

def _generate_image_with_text(image_path, top_text, bottom_text, font_file_name):
    """
    Je génère une image avec textes et police.
    Retourne un ContentFile Django (image avec textes) ou None si erreur.
    Le '_' indique une fonction "privée" à ce module.
    """
    try:
        # J'ouvre et convertis l'image en RGB.
        img = Image.open(image_path).convert('RGB')
        # Objet pour dessiner sur l'image.
        draw = ImageDraw.Draw(img)

        # Je charge la police.
        pil_font = None
        if font_file_name: # Si un nom de fichier de police est fourni.
            try:
                # Chemin complet de la police.
                font_full_path = os.path.join(settings.BASE_DIR, 'fonts', font_file_name)
                # Je charge la police (taille 60px, pourrait être dynamique).
                pil_font = ImageFont.truetype(font_full_path, size=60)
            except IOError: # Si police non trouvée/corrompue.
                print(f"Police '{font_file_name}' non trouvée. J'utilise la police par défaut.")
                pil_font = ImageFont.load_default() # Police par défaut de Pillow.
        else: # Si aucune police n'est spécifiée.
            pil_font = ImageFont.load_default()

        # Dimensions de l'image.
        img_width, img_height = img.size

        # Marges et positions du texte (relatives à la taille de l'image).
        line_spacing_factor = 0.1 # Marge verticale (10% hauteur image).
        text_margin_y = int(img_height * line_spacing_factor)

        text_y_top = text_margin_y # Position Y du texte haut.
        # Position Y du texte bas: du bas, moins marge et hauteur de police.
        text_y_bottom = img_height - text_margin_y - pil_font.getbbox('Ay')[3]

        # Fonction interne pour dessiner le texte avec contour.
        def draw_text_with_outline(text, y_position):
            # Je centre le texte horizontalement.
            x_position = img_width / 2
            outline_color = 'black'
            text_color = 'white'
            # Dessin du contour (4 directions).
            for offset in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
                draw.text((x_position + offset[0], y_position + offset[1]), text, font=pil_font, fill=outline_color, anchor='ms')
            # Dessin du texte principal.
            draw.text((x_position, y_position), text, font=pil_font, fill=text_color, anchor='ms')

        # J'ajoute le texte du haut (majuscules).
        if top_text:
            draw_text_with_outline(top_text.upper(), text_y_top)
        
        # J'ajoute le texte du bas (majuscules).
        if bottom_text:
            draw_text_with_outline(bottom_text.upper(), text_y_bottom)

        # Je sauvegarde l'image générée en mémoire.
        buffer = io.BytesIO() # "Fichier" en mémoire.
        img.save(buffer, format='JPEG') # Sauvegarde en JPEG.
        buffer.seek(0) # "Rembobinage" du buffer.

        # Création d'un ContentFile Django (pour ImageField).
        return ContentFile(buffer.read(), name=f"meme_generated.jpg")

    except Exception as e: # En cas d'erreur.
        print(f"Erreur génération image : {e}")
        return None

# --- Mes Vues --- #
# Fonctions recevant une requête web et retournant une réponse.

def meme_create(request):
    """
    Je gère la création de mèmes.
    GET : affichage formulaire.
    POST : traitement données formulaire.
    """
    # Je récupère les polices disponibles pour le sélecteur.
    available_fonts = get_available_fonts()

    # Je détermine la police par défaut ('Cabilla.ttf' ou la première disponible).
    default_font_filename = 'Cabilla.ttf'
    if not any(font['file'] == default_font_filename for font in available_fonts) and available_fonts:
        default_font_filename = available_fonts[0]['file'] # Première de la liste.
    elif not available_fonts:
        default_font_filename = None # Pillow utilisera sa police par défaut.

    # 'Context' pour passer les données au template HTML.
    context = {
        'fonts': available_fonts,
        'selected_font': default_font_filename, # Police pré-sélectionnée.
        'top_text': '', # Valeur initiale.
        'bottom_text': '' # Valeur initiale.
    }

    if request.method == 'POST': # Si formulaire soumis.
        # Récupération des données.
        original_image_file = request.FILES.get('original_image')
        top_text = request.POST.get('top_text', '').strip() # .strip() enlève espaces inutiles.
        bottom_text = request.POST.get('bottom_text', '').strip()
        selected_font_filename = request.POST.get('font_selection', default_font_filename)

        # Mise à jour du contexte (pour pré-remplir si validation échoue).
        context['top_text'] = top_text
        context['bottom_text'] = bottom_text
        context['selected_font'] = selected_font_filename

        # --- Mes Validations --- #
        # Je vérifie si une image a été fournie.
        if not original_image_file:
            messages.error(request, "Veuillez sélectionner une image.")
            return render(request, 'meme/meme_create.html', context) # Ré-affiche formulaire.

        # Je vérifie si au moins un texte est rempli.
        if not top_text and not bottom_text:
            messages.error(request, "Veuillez remplir au moins un champ de texte (haut ou bas).")
            return render(request, 'meme/meme_create.html', context)
        
        # --- Création et Génération --- #
        # Création de l'instance `Meme` (image originale, textes).
        meme_instance = Meme.objects.create(
            original_image=original_image_file, 
            top_text=top_text, 
            bottom_text=bottom_text
            # 'generated_image' sera rempli plus tard.
        )

        # Appel à ma fonction de génération d'image.
        generated_image_content_file = _generate_image_with_text(
            image_path=meme_instance.original_image.path, # Chemin de l'image originale sauvegardée.
            top_text=top_text, 
            bottom_text=bottom_text, 
            font_file_name=selected_font_filename # Police choisie.
        )

        # Vérification de la réussite de la génération.
        if generated_image_content_file:
            # Sauvegarde de l'image générée et de l'instance Meme.
            meme_instance.generated_image.save(f'meme_{meme_instance.id}.jpg', generated_image_content_file, save=True)
            messages.success(request, "Mème créé avec succès !")
            return redirect('meme_gallery') # Redirection vers la galerie.
        else:
            # En cas d'échec, affichage d'une erreur.
            # Il faudrait idéalement supprimer `meme_instance` ou marquer l'échec.
            messages.error(request, "Erreur lors de la génération de l'image du mème.")
            return render(request, 'meme/meme_create.html', context)

    # Si GET, affichage du formulaire vierge (ou avec valeurs par défaut).
    return render(request, 'meme/meme_create.html', context)

def meme_gallery(request):
    """J'affiche la galerie des mèmes avec image générée."""
    # Je récupère les mèmes (sauf ceux sans image générée), triés par date (plus récent d'abord).
    memes = Meme.objects.exclude(generated_image__exact='').exclude(generated_image__isnull=True).order_by('-created_at')
    # Passage des mèmes au template.
    return render(request, 'meme/meme_gallery.html', {'memes': memes})

# "request": objet Django avec infos de la requête HTTP.
# "render": raccourci Django pour générer HTML (template + données).
