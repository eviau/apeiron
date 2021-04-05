        - scroll: une fct dans Editor() pour ajuster le cx, cy de l'editeur qui est en cours d'utilisation
        - une autre pour ajuster celui de Screen()
        - peut-être une façon de merger les deux...?
        - meme chose pour ERow() et le champ render: peut-être que render devrait être calculé juste avant de le renderer, dans Screen? et pas sauvegarder?

        changer content.row pour content.contents ?

        stop at ligne 270, mercredi 28 octobre 2020
        
        
# 4 avril 2021

 stop at ligne 352, fonction Screen.refresh()
 
 ce qu'il faut, c'est que Kernel soit dans le __init__ de Config, je pense
