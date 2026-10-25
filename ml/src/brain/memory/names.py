"""Compact first-name gender hints for person references."""

MALE = frozenset("""
aaron abdul abel abraham adrian ahmed aiden ajay albert alejandro alex
alexander ali alonso alvin amir andre andrew angel anthony antonio arjun
arthur asher austin benjamin bilal blake bradley brandon brayden brendan
brian bruce caleb cameron carlos carter chad charles chris christian
christopher colin connor cooper daniel david declan dennis derek diego
dominic donovan douglas dylan edgar eduardo elias elijah emmanuel eric
ethan evan ezra felix finn francisco gabriel gavin george grant gregory
hamza harry henry isaac isaiah ismael ivan jack jacob jaden james javier
jayden jeremiah joaquin jose joseph joshua juan julian justin kai karim
keith kenneth kevin khalid kingston kyler larry leo leon liam logan
lorenzo louis lucas luke malachi marcus mario mark martin mason mateo
matthew max michael miguel milo nathan nathaniel nicholas noah omar oscar
owen parker patrick paul pedro peter philip rafael raymond reese richard
river robert roman ronald ryan samuel sebastian sergio seth shane simon
spencer stephen steven taylor theo theodore thomas timothy tomas tristan
tyler victor vincent william xavier zachary zain
abdullah akira aleksei anand andres anwar arman barrett benicio boris
bruno cassian cedric cormac dante darian dev dmitri donte eitan emilio
enrique fabian farid federico ferdinand florin franco haruto hassan
hiroki idris ilya irfan jorge kenji khalil kian kirill klaus laksh
leandro mads mahir manuel marcel marco mateusz mehdi mohammed murat
naveen nikolai nikhil nino otto paolo pietro rami rayan remy rohan
roosevelt salim sami sanjay shiloh srihari tariq thiago ulrich yusuf
""".split())

FEMALE = frozenset("""
abigail ada adeline adriana agnes aisha alana alexandra alice alicia
alina alyssa amara amaya amber amelia amy ana anastasia andrea angelina
anna annabelle ariana ariella arya ashley aubrey audrey aurora ava ayla
beatrice bella bernadette bianca blair brianna brielle brooklyn camila
carla carolina caroline cassandra catherine charlotte chloe claire
clara clementine cora daniela danielle delilah diana elena eliana elise
ella ellie emilia emily emma esther eva evelyn faith fatima felicity
fiona florence freya gabriella gemma genesis gia grace greta guadalupe
hailey hannah harper hazel helena imani ines irene isla ivy jade jasmine
jennifer jessica josephine julia juliana juliette kaitlyn karen katherine
kayla keira kira laura layla leah lena liliana lillian lily lucia lucy
luna madeline madison maeve margaret maria mariana marisol mary matilda
maya mia mila miranda nadia naomi natalia natalie nora olivia ophelia
paige paloma penelope phoebe priya quinn rachel rebecca remi riley rose
rosalie rosa ruby sabrina samantha sara sarah serena sofia sophia stella
summer susan sylvia tessa thea valentina veronica victoria violet vivian
willow yara zoe zora
adele afia ahana aiko alessia alia amina anika anjali anouk apolline
araceli asha ayesha cecilia chiara dakota daria deepa elodie esme
farah fatou georgia hadley hana haruka hina irina jamila jaya jiwoo
kaia kalina kiana kimiko laila lana leila leonie louisa lydia malika
meera mei nadine nisha noor palak rania rhea roxana saoirse sasha
shreya simone soraya tatiana tia yasmin yuki
""".split())


def gender(name: str) -> str | None:
    first = str(name or "").strip().split(maxsplit=1)[0].strip(".,'’-").casefold() \
        if str(name or "").strip() else ""
    if first in MALE:
        return "male"
    if first in FEMALE:
        return "female"
    return None
