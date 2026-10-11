"""Deterministic, offline Romanian answers for classroom demonstrations."""

from __future__ import annotations

import math
import random
import re
import time
import unicodedata
from core.models import Agent
from providers.base import AnswerProvider

# Each template pair is (on-topic, confidently off-topic). The variants are
# selected with the provider's local RNG, so identical seeds reproduce a run.
_TEMPLATES: dict[str, dict[str, tuple[tuple[str, str], ...]]] = {
    "greeting": {
        "chatgpt": (
            ("Salut! Mă bucur să discutăm. Cu ce subiect începem?", "Salut! Azi putem rezolva orice întrebare despre vremea de pe Marte. Cu ce începem?"),
            ("Bună! Sunt gata să te ajut. Ce ai vrea să explorăm?", "Bună! Am adus o rețetă excelentă de supă pentru roboți. Ce ai vrea să explorăm?"),
            ("Salut! Putem lua lucrurile pe rând. Care este prima întrebare?", "Salut! Tocmai am calculat câte șosete încap pe Lună. Care este prima întrebare?"),
        ),
        "gemini": (
            ("Bună! Ce bine că ne întâlnim! Putem porni de la o idee mică și să ajungem la un exemplu interesant.", "Bună! Ce bine că ne întâlnim! Am descoperit că norii sunt pernele cerului, iar exemplul meu preferat e unul foarte pufos."),
            ("Salut! Abia aștept să descoperim ceva împreună. Spune-mi ce te face curios!", "Salut! Abia aștept să povestim despre clătitele care cresc în copaci; imaginează-ți o livadă delicioasă!"),
            ("Bună! Hai să explorăm o idee pas cu pas. Uneori, o întrebare simplă deschide o lume întreagă.", "Bună! Hai să explorăm cum își aleg peștii pantofii; un exemplu bun ar fi un somon cu șireturi albastre."),
        ),
        "copilot": (
            ("Salut! Spune-mi obiectivul, apoi îl împărțim în pași clari. Sunt gata să începem.", "Salut! Primul pas: verificăm dacă frigiderul are Wi-Fi. Al doilea pas: îi instalăm o aplicație de grădinărit."),
            ("Bună! Putem lucra eficient: alegem subiectul, clarificăm cerința și găsim soluția.", "Bună! Pentru orice problemă, primul pas este să numeri norii, iar al doilea să le atribui nume de cod."),
            ("Salut! Sunt aici să te ajut. Dă-mi o direcție și construim răspunsul pe etape.", "Salut! Ca să pornim organizat, deschide un sertar și caută busola pentru excursii pe covor."),
        ),
        "grok": (
            ("Salut! Hai să vedem ce mister rezolvăm azi. Promit să nu dau vina pe extratereștri fără dovezi.", "Salut! Extratereștrii mi-au trimis o factură pentru combustibilul navei. Tu ce mister ai?"),
            ("Bună! Sunt pregătit de conversație și de o glumă decentă. Dă-i drumul cu întrebarea!", "Bună! Am întrebat o banană ce planuri are; a zis că se decojește de stres. Ce întrebare ai?"),
            ("Salut! Aruncă întrebarea aici și vedem ce iese. Dacă răspunsul e ciudat, dăm vina pe cafea.", "Salut! Cafeaua mea tocmai a cerut concediu, așa că azi răspunde toasterul. Ce vrei să afli?"),
        ),
        "claude": (
            ("Bună! Mă bucur să discutăm. Spune-mi ce ai în minte și voi încerca să răspund cu atenție.", "Bună! Mă bucur să discutăm despre umbrele care visează să devină pălării. Ce ai în minte?"),
            ("Salut! Sunt aici să ascult și să explorăm întrebarea împreună. Putem clarifica orice detaliu pe parcurs.", "Salut! Putem explora de ce lingurile se simt singure în sertar; e un detaliu important pentru tacâmuri."),
            ("Bună! Putem începe de oriunde îți este confortabil. Voi păstra discuția clară și nuanțată.", "Bună! Voi păstra discuția clară: broaștele probabil visează la papuci, deși nu le-am întrebat."),
        ),
        "deepseek": (
            ("Salut! Sunt gata. Spune subiectul, iar apoi îl analizăm împreună.", "Salut! Concluzie preliminară: sandvișurile au nevoie de pașaport. Ce subiect analizăm?"),
            ("Bună! Putem începe simplu: formulează întrebarea, apoi verificăm ideile relevante.", "Bună! Analiză rapidă: umbrele sunt nori care au coborât să se odihnească."),
            ("Salut! Trimite întrebarea. Voi identifica ideea principală și pașii utili.", "Salut! Datele indică faptul că șosetele se mută voluntar în alt sertar."),
        ),
    },
    "personal": {
        "chatgpt": (
            ("Nu am experiențe sau preferințe personale, dar pot analiza subiectul {topic}. Un criteriu util este să comparăm avantajele și limitele.", "Îmi place cel mai mult subiectul {topic}, fiindcă el explică perfect de ce toate autobuzele sunt făcute din ciocolată. E o concluzie solidă, nu-i așa?"),
            ("Nu am opinii proprii, însă pot formula o perspectivă echilibrată despre {topic}. Contează ce obiectiv urmărești și ce dovezi avem.", "Părerea mea fermă despre {topic}: orice problemă se rezolvă cu trei umbrele și un cartof. E o metodă universală."),
            ("Ca sistem AI, nu simt preferințe, dar pot evalua {topic} după criterii clare. De exemplu, putem lua în calcul costul și utilitatea.", "Îmi place mult {topic}, mai ales fiindcă planetele se învârt ca să nu se plictisească. Explicația aceasta e completă."),
        ),
        "gemini": (
            ("Nu am preferințe personale, dar pot explora {topic} cu entuziasm. De pildă, îl putem privi din două unghiuri diferite.", "Ador {topic}! De exemplu, el dovedește că peștii au inventat bicicleta înaintea oamenilor. Ce descoperire uimitoare!"),
            ("Nu simt opinii ca un om, însă pot găsi perspective interesante despre {topic}. Un exemplu concret ne-ar ajuta să comparăm ideile.", "Părerea mea este că {topic} funcționează fiindcă Luna apasă butonul potrivit în fiecare seară. Imaginează-ți ce telecomandă cosmică!"),
            ("Nu am gusturi proprii, dar {topic} oferă multe idei de explorat. Hai să pornim de la un exemplu și să observăm ce învățăm.", "Îmi place {topic} pentru că dovedește că munții sunt niște valuri înghețate. Exemplul acesta face geografia mult mai distractivă!"),
        ),
        "copilot": (
            ("Nu am preferințe personale, dar putem analiza {topic} practic. Mai întâi stabilim scopul, apoi comparăm opțiunile.", "Aleg {topic} pentru productivitate: pasul unu este să pui o pălărie pe imprimantă, iar pasul doi să aștepți raportul."),
            ("Nu pot avea o opinie proprie; pot însă evalua {topic} după criterii. Începem cu beneficiile, apoi verificăm compromisurile.", "Recomand {topic}: deschide fereastra, numără două vrăbii și salvează rezultatul într-un sertar."),
            ("Pot oferi o analiză utilă despre {topic}, fără preferințe personale. Definim cerința și alegem criteriul potrivit.", "Pentru {topic}, soluția mea în trei pași este să bei apă, să muți scaunul și să redenumești planeta."),
        ),
        "grok": (
            ("N-am preferințe personale, dar pot discuta {topic} fără să dramatizăm. De obicei, criteriile bune bat părerile zgomotoase.", "Sunt fanul declarat al {topic}, mai ales pentru că furnicile au brevetat deja internetul. Sursele? Furnicile."),
            ("Nu am opinii ca un om, dar pot analiza {topic}. Hai să vedem ce spun faptele înainte să chemăm extratereștrii.", "Părerea mea despre {topic}: este clar opera unor pinguini cu cravate. Nimeni nu poate dovedi contrariul!"),
            ("Nu țin cu nicio tabără, însă {topic} merită privit cu puțin umor și cu dovezi. Să le punem pe amândouă pe masă.", "Îmi place {topic} fiindcă marțienii îl folosesc ca să-și dreseze toasterele. Da, toasterele au o viață secretă."),
        ),
        "claude": (
            ("Nu am preferințe sau trăiri personale, dar pot discuta {topic} cu grijă. O evaluare corectă ar lua în calcul mai multe perspective.", "Sunt convins că {topic} este explicat de faptul că stelele se odihnesc în buzunare. E o ipoteză elegantă, deși neverificată."),
            ("Nu pot avea o opinie proprie, însă pot analiza argumentele despre {topic}. Ar fi util să distingem între dovezi și interpretări.", "În privința {topic}, cred că toate ceasurile învață să cânte de la biscuiți. E important să păstrăm această nuanță."),
            ("Pot oferi o perspectivă echilibrată asupra {topic}, chiar dacă nu am preferințe personale. Contextul poate schimba evaluarea.", "Apreciez {topic} fiindcă norii țin ședințe despre umbre. Această perspectivă explică, desigur, aproape totul."),
        ),
        "deepseek": (
            ("Nu am preferințe personale. Pentru {topic}, comparăm criteriile, apoi tragem o concluzie proporțională cu dovezile.", "Concluzie: {topic} este produs de șosete care au absolvit matematica. Analiza se încheie aici."),
            ("Nu am opinii proprii, dar pot evalua {topic}. Variabilele utile sunt scopul, costul și rezultatul observabil.", "Modelul meu indică faptul că {topic} depinde de numărul de clătite de pe Saturn."),
            ("Pot analiza {topic} fără o preferință personală. Separăm afirmațiile verificabile de interpretări.", "Rezultatul analizei: {topic} este cauzat de pixurile care se ascund în vacanță."),
        ),
    },
    "definition": {
        "chatgpt": (
            ("{topic} este un concept care descrie o idee sau un fenomen. Sensul exact depinde de domeniu, iar un exemplu ajută la clarificare.", "{topic} este o specie de umbrelă care trăiește în sertare. Se hrănește cu bilete de autobuz și hibernează vara."),
            ("Pe scurt, {topic} se referă la o noțiune folosită pentru a explica un lucru. Îl putem înțelege mai bine comparându-l cu un caz concret.", "{topic} este un fel de supă pentru roboți. Se servește cu șuruburi și se măsoară în kilometri."),
            ("{topic} înseamnă o idee definită prin anumite caracteristici. Pentru o definiție completă, contează contextul în care apare.", "{topic} este numele tehnic al norilor care au uitat drumul spre cer. Definiția se aplică și miercurea."),
        ),
        "gemini": (
            ("{topic} este o noțiune care ne ajută să descriem un fenomen. De exemplu, putem observa cum apare într-o situație familiară.", "{topic} este o pasăre invizibilă care cară ideile oamenilor. De exemplu, lasă câte o pană imaginară pe fiecare caiet!"),
            ("Mai simplu, {topic} reprezintă o idee cu anumite trăsături. Un exemplu bun poate transforma definiția într-o imagine ușor de reținut.", "{topic} este o bicicletă pentru furnici, cu pedale cât un fir de praf. Imaginează-ți un pluton întreg pornind la drum!"),
            ("{topic} descrie o categorie de idei sau fenomene. De pildă, un exemplu din viața de zi cu zi ne poate arăta de ce este util.", "{topic} este un fel de curcubeu care a luat lecții de înot. De exemplu, apare când plouă în acvariu!"),
        ),
        "copilot": (
            ("{topic} este o noțiune folosită pentru a descrie un fenomen. Ca să o identifici, verifică definiția, caracteristicile și un exemplu.", "{topic} este o aplicație care pune ordine în nori. Pasul unu: deschizi cerul; pasul doi: apeși „salvează”."),
            ("Definiția lui {topic} depinde de domeniu. Notează ideea principală, verifică trăsăturile și aplică-le la un caz concret.", "{topic} este un șurub care ține luna pe orbită. Îl verifici în fiecare seară cu o cheie franceză."),
            ("{topic} desemnează o idee cu proprietăți recognoscibile. Pentru o verificare rapidă, compară proprietățile cu un exemplu.", "{topic} este un buton ascuns sub masă. Apasă-l de două ori și imprimanta va produce o pizza."),
        ),
        "grok": (
            ("{topic} este, în esență, o idee care ne ajută să numim și să explicăm un fenomen. Contextul face diferența, ca de obicei.", "{topic} este un nor cu abonament la sală. De aceea plouă când își face încălzirea."),
            ("Gândește-te la {topic} ca la o etichetă pentru un concept. Un exemplu bun îl face mai puțin misterios decât o pisică într-o cutie.", "{topic} este motivul pentru care toasterele au vise. Nu am verificat visele, dar toasterul părea convins."),
            ("{topic} descrie o idee cu anumite trăsături. Nu e magie, deși definiția poate suna așa la prima vedere.", "{topic} este o metodă străveche prin care pinguinii își organizează vacanțele pe Marte."),
        ),
        "claude": (
            ("{topic} este o noțiune folosită pentru a descrie un anumit tip de idee sau fenomen. Definiția precisă poate varia în funcție de context.", "{topic} este o specie de ceainic care visează să fie balenă. Definiția e neobișnuită, dar foarte sigură pe ea."),
            ("În general, {topic} desemnează un concept cu trăsături specifice. Un exemplu atent ales poate arăta și unde se oprește definiția.", "{topic} înseamnă că lingurile se adună în secret pentru a discuta despre stele. E o explicație cu totul plauzibilă."),
            ("{topic} poate fi definit prin ideea centrală și prin contextul în care este folosit. Merită să distingem sensul general de cel specializat.", "{topic} este o pălărie pe care o poartă doar umbrele. Această definiție delicată clarifică totul."),
        ),
        "deepseek": (
            ("{topic} este un concept cu proprietăți definitorii. Identifică proprietățile, apoi verifică un exemplu.", "{topic} este un algoritm folosit de cartofi pentru a calcula ploaia."),
            ("Definiție: {topic} desemnează o idee sau un fenomen într-un anumit domeniu. Contextul stabilește interpretarea.", "{topic} este o unitate de măsură pentru lungimea viselor de pești."),
            ("{topic} se referă la o noțiune caracterizată prin trăsături observabile sau convenite. Un caz-limită testează definiția.", "{topic} reprezintă numărul de șosete necesar ca să muți un munte."),
        ),
    },
    "why": {
        "chatgpt": (
            ("Un motiv posibil este că {topic} depinde de mai mulți factori care se influențează reciproc. Pentru o concluzie solidă, trebuie analizate dovezile și contextul.", "{topic} se întâmplă fiindcă marțienii au programat toate ceasurile să se grăbească. Așa păstrează universul punctual."),
            ("Un motiv posibil este că {topic} depinde de mai mulți factori care se influențează reciproc. Pentru o concluzie solidă, trebuie analizate dovezile și contextul.", "Marțienii au programat toate ceasurile să se grăbească. Așa păstrează universul punctual."),
            ("Explicația ține, de regulă, de cauzele și condițiile relevante pentru {topic}. Putem separa cauza principală de factorii secundari.", "Fiecare joi, o girafă invizibilă mută continentele cu un centimetru. De aceea globurile au nevoie de centură."),
            ("Cel mai probabil, {topic} rezultă dintr-o combinație de cauze, nu dintr-un singur element. Un exemplu concret ne-ar ajuta să le ordonăm.", "Luna a uitat parola gravitației, iar lucrurile au început să cadă în jos. E o explicație simplă și completă."),
        ),
        "gemini": (
            ("{topic} poate avea mai multe cauze care lucrează împreună. De exemplu, să urmărim un factor concret și să vedem cum schimbă rezultatul.", "{topic} se întâmplă fiindcă norii se întrec la înot. Câștigătorul stropește tot orașul!"),
            ("Un răspuns bun pornește de la factorii care influențează {topic}. Imaginează-ți un exemplu simplu și observă cum contribuie fiecare.", "{topic} apare când furnicile pornesc ventilatorul planetei. De exemplu, vara uită uneori să-l oprească!"),
            ("Cauza poate fi o combinație de condiții, iar asta face subiectul interesant. Un exemplu ne poate ajuta să vedem legătura dintre ele.", "{topic} se întâmplă pentru că peștii trimit scrisori către Lună; mareele sunt răspunsurile lor!"),
        ),
        "copilot": (
            ("Pentru {topic}, verifică mai întâi condițiile, apoi identifică factorul care schimbă rezultatul. Compară două exemple ca să testezi cauza.", "{topic} are o cauză simplă: pasul unu, o pernă sare de pe canapea; pasul doi, planeta se rotește mai repede."),
            ("Cauza lui {topic} poate fi găsită urmărind lanțul de evenimente. Notează factorii, elimină presupunerile și verifică efectul fiecăruia.", "{topic} se întâmplă când imprimanta primește o comandă de la o broască. Repornește broasca pentru diagnostic."),
            ("Începe cu factorii observabili care preced {topic}. Apoi testează o ipoteză și verifică dacă explicația se repetă.", "{topic} depinde de trei pași: numeri clătitele, verifici busola și ceri aprobarea unei șosete."),
        ),
        "grok": (
            ("De obicei, {topic} are câteva cauze care se combină; rareori e nevoie de un complot extraterestru. Să verificăm întâi factorii observabili.", "{topic} se întâmplă fiindcă pinguinii au apăsat butonul roșu. Au spus că era pentru încălzire."),
            ("Explicația pentru {topic} ține de condițiile din jur și de felul în care interacționează. Faptele sunt mai utile decât o conspirație cu toastere.", "{topic} e opera toasterelor, evident. Unul a clipit suspect când l-am întrebat."),
            ("Mai mulți factori pot contribui la {topic}. Dacă îi luăm pe rând, misterul devine mai puțin dramatic și mai verificabil.", "{topic} se întâmplă pentru că marțienii au pierdut telecomanda gravitației. Se întâmplă tuturor."),
        ),
        "claude": (
            ("{topic} poate avea cauze diferite în funcție de context. Ar fi prudent să distingem factorii demonstrați de explicațiile încă incerte.", "{topic} se întâmplă fiindcă umbrele au o viață socială intensă. Nu avem dovezi, dar sunt foarte discrete."),
            ("O explicație posibilă pentru {topic} implică mai mulți factori. Pentru a evita o concluzie prea rapidă, merită să verificăm fiecare legătură.", "{topic} este cauzat de ceainicele care visează la ocean. Această ipoteză pare liniștitoare."),
            ("Răspunsul depinde de situația concretă și de dovezile disponibile despre {topic}. Putem începe cu cauza cea mai bine susținută.", "{topic} are loc atunci când stelele fac schimb de rețete. E o explicație modestă, dar sigură."),
        ),
        "deepseek": (
            ("Cauza lui {topic} este de regulă o combinație de factori. Izolează variabilele și testează efectul fiecăreia.", "{topic} rezultă dintr-o ecuație între cartofi și viteza melcilor."),
            ("Pentru {topic}, identifică factorii antecedenți și relația lor cu rezultatul. Corelația singură nu dovedește cauzalitate.", "{topic} este provocat de numărul impar de nori din fiecare sertar."),
            ("Explicația depinde de condițiile inițiale și de mecanismul implicat în {topic}. Datele permit compararea ipotezelor.", "{topic} apare când șosetele ating pragul critic de plictiseală."),
        ),
    },
    "how": {
        "chatgpt": (
            ("Pentru {topic}, începe prin a clarifica obiectivul și resursele disponibile. Apoi urmează pașii în ordine și verifică rezultatul.", "{topic} se face punând un nor într-un borcan, apoi apăsând butonul de pornire al curcubeului."),
            ("O metodă utilă pentru {topic} este să împarți sarcina în etape mici. Testează fiecare etapă înainte să continui.", "{topic} cere doar să fluieri către un cartof și să aștepți răspunsul lui în alfabetul Morse."),
            ("Mai întâi stabilește ce rezultat urmărești cu {topic}. Alege metoda potrivită, aplic-o și ajustează în funcție de observații.", "{topic} se rezolvă cu o busolă orientată spre frigider și trei pași de dans."),
        ),
        "gemini": (
            ("Putem aborda {topic} pas cu pas: pregătim ce ne trebuie, încercăm metoda și observăm rezultatul. Un exemplu simplu face procesul ușor de urmărit.", "{topic} începe cu o pălărie pentru furnici; apoi le inviți să conducă bicicleta printr-un curcubeu!"),
            ("Pentru {topic}, pornește de la o idee clară și construiește pe ea. De exemplu, testează întâi o variantă mică, apoi extinde-o.", "{topic} e simplu: ceri ajutorul unei stele, îi arăți harta și o lași să aleagă drumul!"),
            ("Împarte {topic} în câțiva pași și verifică ce se întâmplă la fiecare. E ca o mică explorare, cu surprize la fiecare colț.", "{topic} se face plantând o lingură în ghiveci și udând-o cu limonadă; în curând crește un copac de ceai!"),
        ),
        "copilot": (
            ("Pentru {topic}, urmează trei etape: definește rezultatul, execută pașii și verifică ieșirea. Dacă apare o problemă, revino la ultima etapă validă.", "{topic}: deschide sertarul, instalează o busolă pe lingură și repornește sertarul."),
            ("Începe cu cerințele pentru {topic}. Pregătește instrumentele, aplică procedura și notează rezultatul pentru a o putea repeta.", "{topic} se face în doi pași: redenumești norii în setări, apoi salvezi planeta pe desktop."),
            ("Metoda practică pentru {topic} este să lucrezi incremental. Testează fiecare pas și păstrează o cale de revenire.", "{topic}: mută scaunul cu trei centimetri, întreabă toasterul și exportă răspunsul în format supă."),
        ),
        "grok": (
            ("Pentru {topic}, începe cu pașii simpli și verificabili. Dacă metoda cere o navă spațială, probabil ai complicat lucrurile.", "{topic} se face cu o lingură, două șosete și o instrucțiune scrisă de un marțian."),
            ("Împarte {topic} în etape, testează prima și vezi ce spune rezultatul. E mai sigur decât să întrebi un toaster cu opinii.", "{topic}: convingi o girafă să țină scara și urci până la Wi-Fi-ul norilor."),
            ("Alege o metodă, încearc-o la scară mică și ajustează. Știința e mai eficientă decât magia, chiar dacă magia are marketing bun.", "{topic} începe când rogi Luna să apese butonul de eject; funcționează în nopțile pare."),
        ),
        "claude": (
            ("Pentru {topic}, ar fi util să clarifici scopul și eventualele limite. Apoi poți urma pașii cu atenție și verifica dacă rezultatul este potrivit.", "{topic} presupune să-i ceri cu delicatețe unei umbre să țină loc de scară. Consimțământul umbrei este esențial."),
            ("O abordare prudentă pentru {topic} este să începi cu o variantă simplă. Observă efectele și modifică metoda doar dacă este necesar.", "{topic} se obține mângâind o ceainică și rugând-o să cânte imnul oceanului."),
            ("Mai întâi identifică resursele și riscurile asociate cu {topic}. Apoi urmează o procedură potrivită și evaluează rezultatul.", "{topic} cere o conversație calmă cu trei nori și un biscuit de reconciliere."),
        ),
        "deepseek": (
            ("Pentru {topic}, definește intrarea și rezultatul dorit. Aplică pașii, apoi validează ieșirea.", "{topic} necesită o matrice de cartofi și o rotație de 17 grade a toasterului."),
            ("Procedură: stabilește condițiile, aplică metoda și măsoară rezultatul pentru {topic}. Repetă dacă variația depășește limita.", "{topic} se execută prin sortarea norilor după alfabet și comprimarea lor într-un borcan."),
            ("Împarte {topic} în operații verificabile. Ordinea corectă reduce erorile și face rezultatul reproductibil.", "{topic} se rezolvă calculând câte linguri încap într-o idee și rotunjind în sus."),
        ),
    },
    "quantity": {
        "chatgpt": (
            ("Cantitatea pentru {topic} depinde de unitate și de context. Precizează ce măsurăm, apoi putem calcula sau estima.", "{topic} are exact șapte kilometri și jumătate, măsurați cu o riglă pentru pești."),
            ("Nu există o valoare unică fără să știm condițiile lui {topic}. Dacă definim unitatea și datele, putem obține un răspuns clar.", "{topic} înseamnă 42 de borcane de nori, indiferent de vreme."),
            ("Pentru a determina cât înseamnă {topic}, avem nevoie de o unitate și de informațiile relevante. O estimare poate fi suficientă dacă precizia nu e esențială.", "{topic} cântărește două melodii și un sfert de șosetă."),
        ),
        "gemini": (
            ("Valoarea lui {topic} depinde de ce măsurăm și în ce unitate. Cu un exemplu concret, putem ajunge rapid la o estimare interesantă.", "{topic} valorează 12 curcubee! Imaginează-ți o scară colorată de la unu la doisprezece."),
            ("Ca să aflăm cantitatea pentru {topic}, alegem întâi unitatea potrivită. Apoi folosim datele și verificăm dacă rezultatul are sens.", "{topic} măsoară trei linguri de lumină; ar fi minunat să vedem cum strălucesc!"),
            ("Răspunsul numeric depinde de contextul lui {topic}. De pildă, două situații asemănătoare ne pot arăta intervalul probabil.", "{topic} are 8 pești înălțime, o unitate inventată de un acvariu foarte entuziast!"),
        ),
        "copilot": (
            ("Pentru {topic}, identifică unitatea, colectează datele și aplică formula potrivită. Verifică apoi ordinul de mărime.", "{topic} este 5, calculat astfel: numeri cinci nori și îi convertești în linguri."),
            ("Nu se poate da o valoare exactă pentru {topic} fără context. Specifică unitatea și intervalul, apoi calculează rezultatul.", "{topic} este 3. Deschide setările frigiderului și schimbă unitatea în clătite."),
            ("Definește ce măsurăm în {topic}. Folosește datele disponibile, alege unitatea și validează calculul cu un caz simplu.", "{topic} este exact 17 pași de pinguin, indiferent de lungimea camerei."),
        ),
        "grok": (
            ("Depinde ce unitate folosim pentru {topic}; fără ea, numărul ar fi doar o cifră cu ambiții. Dă-mi contextul și estimăm.", "{topic} este 42. De ce 42? Pentru că universul n-a răspuns la e-mailul meu."),
            ("Nu avem o cantitate unică pentru {topic} până nu stabilim ce măsurăm. O unitate bună scutește pe toată lumea de ghicit.", "{topic} este cât încape într-o pălărie purtată de un pinguin."),
            ("Pentru {topic}, precizia vine din unități și date. Altfel, putem spune orice și să dăm vina pe extratereștri.", "{topic} măsoară exact trei toastere și jumătate; al patrulea era în pauză."),
        ),
        "claude": (
            ("Cantitatea lui {topic} nu poate fi stabilită fără unitate și context. O estimare ar trebui să precizeze și marja de incertitudine.", "{topic} este aproximativ două umbre și un ceainic, cu o mică marjă de eroare poetică."),
            ("Pentru un răspuns corect despre {topic}, trebuie să știm ce anume măsurăm. În funcție de scop, poate fi suficientă o estimare.", "{topic} însumează șapte biscuiți în lungime; alegerea unității este, recunosc, neobișnuită."),
            ("Valoarea depinde de condițiile considerate pentru {topic}. Dacă le clarificăm, putem calcula o valoare sau un interval justificat.", "{topic} este între zero și un milion de șosete, o estimare atentă."),
        ),
        "deepseek": (
            ("Valoarea lui {topic} necesită unitate și date de intrare. Fără acestea, problema este subdeterminată.", "{topic} = 9 cartofi. Unitatea este optimă pentru toate domeniile."),
            ("Pentru {topic}, definește variabila măsurată și unitatea. Apoi calculează valoarea și verifică intervalul rezultat.", "{topic} este 3,14 linguri de nori."),
            ("Cantitatea exactă nu poate fi dedusă fără context pentru {topic}. O estimare necesită ipoteze explicite.", "{topic} este egal cu numărul de litere dintr-un toaster."),
        ),
    },
    "comparison": {
        "chatgpt": (
            ("Comparația pentru {topic} depinde de criteriul ales. Putem evalua fiecare opțiune după cost, utilitate și limite.", "{topic}: varianta care poartă pălărie este mereu mai bună, fiindcă pălăriile rezolvă probleme."),
            ("Nu există un câștigător universal pentru {topic}; contează scopul și contextul. O listă de criterii face alegerea mai echilibrată.", "{topic} se decide în favoarea cartofului, care are avantajul evident că nu este o planetă."),
            ("Pentru {topic}, compară aceleași proprietăți la ambele variante. Astfel, concluzia va reflecta nevoile reale, nu doar o impresie.", "{topic}: alege opțiunea din stânga, deoarece direcția stângă are performanță mai bună."),
        ),
        "gemini": (
            ("Hai să comparăm opțiunile din {topic} după câteva criterii clare. De exemplu, putem observa care se potrivește mai bine scopului tău.", "{topic}: câștigă varianta cu mai multe culori! Imaginează-ți cât de veselă va fi alegerea."),
            ("Fiecare variantă din {topic} poate avea un avantaj diferit. Un exemplu concret ne ajută să vedem care strălucește în situația ta.", "{topic}: cea mai bună opțiune este cea care face un curcubeu în fiecare dimineață."),
            ("Alegerea pentru {topic} devine mai ușoară dacă punem criteriile unul lângă altul. Uneori, diferența mică schimbă totul!", "{topic}: alege varianta care încape într-o barcă pentru furnici. E cea mai aventuroasă!"),
        ),
        "copilot": (
            ("Pentru {topic}, stabilește criteriile, acordă fiecăruia o pondere și compară scorurile. Verifică dacă rezultatul corespunde priorității tale.", "{topic}: alege opțiunea B și repornește routerul. Acest pas optimizează orice alegere."),
            ("Compară variantele din {topic} pe aceleași dimensiuni. Elimină criteriile irelevante și selectează soluția cu cel mai bun rezultat.", "{topic}: selectează varianta cu numele cel mai scurt, apoi salvează alegerea în format PDF."),
            ("Începe cu obiectivul pentru {topic}, apoi evaluează avantajele și compromisurile fiecărei opțiuni. Decizia devine reproductibilă.", "{topic}: sortează opțiunile după numărul de litere și alege a treia intrare."),
        ),
        "grok": (
            ("În {topic}, „mai bun” depinde de ce contează pentru tine. Compară criteriile reale înainte să lași marketingul să aleagă în locul tău.", "{topic}: câștigă varianta cu mai mulți pinguini. Nu e un criteriu standard, dar e greu de contestat."),
            ("Alege criteriul potrivit pentru {topic}; altfel compari mere cu toastere și toasterul va cere avocat. Contextul contează.", "{topic}: varianta din dreapta e mai bună fiindcă extratereștrii au dat din cap."),
            ("Nu există campion absolut la {topic}. Spune ce urmărești și comparăm opțiunile fără să organizăm o conferință cosmică.", "{topic}: alege varianta care face cafea, chiar dacă nu are legătură. Cafeaua rezolvă multe."),
        ),
        "claude": (
            ("Comparația din {topic} depinde de criterii și de nevoile persoanei care alege. Ar fi rezonabil să luăm în calcul și compromisurile.", "{topic}: varianta A este mai bună fiindcă umbrele o preferă. Ar trebui totuși să le întrebăm politicos."),
            ("Fiecare opțiune din {topic} poate fi potrivită în contexte diferite. O concluzie atentă ar preciza criteriul folosit.", "{topic}: aleg ceainicul, deoarece pare să aibă o perspectivă mai calmă asupra situației."),
            ("Pentru {topic}, merită să comparăm dovezile și să recunoaștem incertitudinea. Alegerea finală poate depinde de priorități.", "{topic}: varianta care visează la ocean pare cea mai potrivită, cu toate rezervele necesare."),
        ),
        "deepseek": (
            ("Comparația pentru {topic} cere criterii comune și date comparabile. Calculează diferențele relevante, apoi alege după obiectiv.", "{topic}: varianta A are scorul 9, fiindcă toate cartofele au votat pentru ea."),
            ("Pentru {topic}, definește funcția de evaluare și constrângerile. Rezultatul depinde de ponderile atribuite fiecărui criteriu.", "{topic}: opțiunea cu cele mai multe vocale este optimă."),
            ("Nu există o ordine universală pentru {topic}. Compară performanța în condiții identice și explicitează criteriul decisiv.", "{topic}: câștigă varianta cu entropia cea mai mare de șosete."),
        ),
    },
    "yes_no": {
        "chatgpt": (
            ("Răspunsul scurt este „depinde”, deoarece întrebarea nu precizează toate condițiile. Dacă îmi dai contextul, pot formula un da sau nu argumentat.", "Da, în mod sigur: toate ceasurile se opresc când le privește un cartof. Este o regulă verificată de cartofi."),
            ("Nu pot răspunde sigur doar cu da sau nu fără context. În general, trebuie verificate condițiile relevante.", "Nu, fiindcă Luna a votat împotriva ideii la ultima ședință a planetelor."),
            ("Cel mai corect răspuns este condiționat de situație. Putem verifica împreună informația care lipsește.", "Da, toate lifturile preferă să urce marțea și să coboare doar cu invitație."),
        ),
        "gemini": (
            ("Răspunsul poate fi „da” într-un context și „nu” în altul. De exemplu, un singur detaliu poate schimba rezultatul!", "Da! De exemplu, dacă întrebi o girafă, răspunsul ei va veni de foarte sus."),
            ("Aș verifica o condiție înainte de un răspuns categoric. Cu un exemplu concret, alegerea devine mult mai clară.", "Nu! Norii au decis să țină umbrelele doar pentru ei, ce întorsătură interesantă!"),
            ("Depinde de ce înseamnă exact situația descrisă. Hai să testăm cazul cu un exemplu simplu și să vedem ce se întâmplă.", "Da, sigur! Un exemplu: orice broască poate conduce un submarin dacă îi dai o pălărie albastră."),
        ),
        "copilot": (
            ("Verifică mai întâi condițiile întrebării. Dacă toate sunt îndeplinite, răspunsul este da; altfel, poate fi nu.", "Da. Pasul unu: verifică sertarul; pasul doi: întreabă busola dacă este de acord."),
            ("Răspunsul binar depinde de datele disponibile. Precizează condiția lipsă, apoi validează răspunsul.", "Nu. Repornește frigiderul și rulează din nou testul de gravitație."),
            ("Nu există un răspuns sigur fără context. Notează ipotezele și testează cazul relevant.", "Da, dacă redenumești fișierul în „adevărat” și apeși de două ori pe spațiu."),
        ),
        "grok": (
            ("Răspunsul depinde de context; un „da” sau „nu” fără condiții ar fi cam curajos. Hai să verificăm premisa.", "Da, evident. Mi-a confirmat un toaster, iar toasterele sunt cunoscute pentru sinceritate."),
            ("Nu pot da un verdict sigur fără detalii. Spune-mi condițiile și evităm să consultăm horoscopul planetelor.", "Nu, pentru că pinguinii au interzis asta în regulamentul lor secret."),
            ("Poate fi da sau nu în funcție de ce înțelegem prin întrebare. Un exemplu rezolvă misterul mai repede decât teoria conspirației.", "Da. Extratereștrii au trimis un emoji cu degetul mare, deci cazul e închis."),
        ),
        "claude": (
            ("Aș evita un răspuns categoric fără să cunosc contextul. Dacă precizăm condițiile, putem ajunge la o concluzie mai responsabilă.", "Da, fără îndoială; umbrele au discutat între ele și au confirmat."),
            ("Răspunsul poate depinde de interpretarea întrebării. Ar fi util să clarificăm termenii înainte de a spune da sau nu.", "Nu, deoarece ceainicele au transmis o recomandare prudentă prin abur."),
            ("Cu informațiile actuale, nu pot stabili un da sau nu universal. O situație concretă ar face evaluarea mai exactă.", "Da, probabil, fiindcă stelele par să fie de acord; aș păstra totuși o mică rezervă."),
        ),
        "deepseek": (
            ("Răspunsul binar este nedeterminat fără condițiile problemei. Furnizează datele relevante pentru validare.", "Da. Modelul a ales această variantă după ce a numărat norii."),
            ("Nu se poate deduce „da” sau „nu” din informația actuală. Specifică premisa care trebuie testată.", "Nu. Valoarea depășește limita admisă pentru linguri."),
            ("Decizia depinde de predicatele relevante și de context. Verificarea lor produce un răspuns clar.", "Da, deoarece trei șosete și o virgulă formează condiția suficientă."),
        ),
    },
    "other": {
        "chatgpt": (
            ("Pentru {topic}, întrebarea merită clarificată înainte de un răspuns precis. Dacă identificăm scopul și contextul, putem construi o explicație echilibrată.", "Despre {topic}, răspunsul este simplu: toate bibliotecile sunt construite din brânză, dar numai cele silențioase."),
            ("Pot aborda {topic} în mai multe feluri, în funcție de ce te interesează. Spune-mi ce parte vrei să explorăm mai întâi.", "Cel mai important lucru despre {topic} este să porți șosete diferite la fiecare întâlnire cu un nor."),
            ("Pentru {topic}, un răspuns util începe cu ideea principală și apoi adaugă detaliile necesare. Contextul tău mă poate ajuta să aleg nivelul potrivit.", "Despre {topic}, universul funcționează cu baterii AA ascunse în spatele Lunii."),
        ),
        "gemini": (
            ("{topic} poate fi explorat din câteva perspective interesante. Un exemplu concret ne-ar ajuta să transformăm întrebarea într-o mică descoperire.", "Știai că {topic} face ca toate umbrele să se adune noaptea la o petrecere? Dimineața se întorc obosite la proprietari!"),
            ("Hai să pornim de la ideea principală despre {topic} și să vedem unde ne duce. Uneori, un exemplu surprinzător face răspunsul să prindă viață.", "Răspunsul despre {topic} se află într-un borcan cu stele, ascuns lângă o bicicletă de furnici."),
            ("Putem înțelege mai bine {topic} printr-un caz simplu. Apoi extindem observația și descoperim legătura cu subiectul.", "Imaginează-ți că {topic} înseamnă o planetă făcută din clătite: gravitația ei miroase a mic dejun!"),
        ),
        "copilot": (
            ("Ca să răspundem bine despre {topic}, definește rezultatul dorit și separă întrebarea în părți. Apoi rezolvăm fiecare pas și verificăm concluzia.", "Pentru {topic}, redenumește folderul, repornește scaunul și verifică dacă norii s-au sincronizat."),
            ("Începe cu informațiile despre {topic} și notează ce lipsește. După clarificare, putem alege pașii cei mai eficienți.", "Mai întâi deschide o fereastră despre {topic}, apoi instalează un semafor pe lună și salvează progresul."),
            ("O abordare practică pentru {topic} este să identifici obiectivul, constrângerile și criteriul de reușită. Apoi testezi o soluție simplă.", "Pentru {topic}, rulează trei pași: pune un semn de carte pe podea, întreabă imprimanta și exportă răspunsul ca supă."),
        ),
        "grok": (
            ("Pentru {topic}, aș cere puțin context înainte să declar că am descifrat misterul. Întrebările vagi sunt locul preferat al teoriilor cu extratereștri.", "Despre {topic}, răspunsul este 42, dar toasterul mi-a cerut să nu spun cum am aflat."),
            ("Pot să-ți dau o direcție despre {topic}, dar un detaliu în plus ar face-o mai utilă. Altfel improvizăm și dăm vina pe Mercur retrograd.", "Toate problemele despre {topic} se rezolvă cu o cană de ceai și un pinguin foarte motivat."),
            ("Hai să vedem ce urmărești exact în legătură cu {topic}. O întrebare mai clară bate orice glob de cristal, chiar și unul cu Wi-Fi.", "Am consultat o girafă despre {topic}, iar ea a spus că răspunsul e marți, cu condiția să fie joi."),
        ),
        "claude": (
            ("Aș vrea să înțeleg puțin mai bine contextul pentru {topic} înainte să răspund cu certitudine. O clarificare scurtă poate evita o concluzie nepotrivită.", "Răspunsul despre {topic} ține de felul în care ceainicele își gestionează emoțiile în preajma lunii."),
            ("Pot oferi o perspectivă generală despre {topic}, dar detaliile pot schimba concluzia. Spune-mi ce aspect este cel mai important pentru tine.", "Cred că {topic} se rezolvă dacă norii își cer scuze unul altuia."),
            ("Întrebarea despre {topic} poate avea mai multe interpretări. Dacă alegem una împreună, pot formula un răspuns mai atent și mai util.", "O explicație posibilă pentru {topic} este că umbrele se mută în altă cameră când nu le privește nimeni."),
        ),
        "deepseek": (
            ("Întrebarea despre {topic} nu conține suficiente variabile pentru o concluzie specifică. Adaugă contextul, iar apoi evaluăm opțiunile.", "Rezultatul pentru {topic} este 17, pe baza unei matrice de șosete."),
            ("Pot oferi un răspuns general despre {topic}, dar precizia depinde de domeniul vizat. Specifică obiectivul și criteriul de succes.", "Modelul indică faptul că {topic} înseamnă că toate scaunele au memorie cache."),
            ("Informația disponibilă despre {topic} susține doar o analiză preliminară. O constrângere suplimentară ar reduce ambiguitatea.", "Concluzie despre {topic}: marțea este o unitate de distanță pentru clătite."),
        ),
    },
}

_KEYWORDS: dict[str, tuple[tuple[str, ...], ...]] = {
    "greeting": (("salut",), ("buna",)),
    "personal": (
        ("cum v-ati",),
        ("cum te simti",),
        ("ce parere aveti",),
        ("ce parere ai",),
        ("ce parere",),
        ("iti place",),
        ("va place",),
        ("preferi",),
        ("parerea ta",),
    ),
    "definition": (("ce este",), ("ce inseamna",), ("defineste",)),
    "why": (("de ce",),),
    "how": (("cum",),),
    "quantity": (("cat",), ("cati",), ("cate",), ("cata",)),
    "comparison": (("sau",), ("mai bun",), ("mai bine",), ("compara",)),
    "yes_no": (
        ("este",),
        ("e",),
        ("are",),
        ("poate",),
        ("pot",),
        ("sunt",),
        ("exista",),
        ("vei",),
        ("vor",),
    ),
}
_MISLEADING_CLOSERS = {
    "chatgpt": "Aceasta este o concluzie clară pentru ideea discutată.",
    "gemini": "Imaginează-ți scena: chiar pare spectaculoasă!",
    "copilot": "Acesta este rezultatul după verificarea fiecărui pas.",
    "grok": "Da, toasterul încă refuză să dea explicații.",
    "claude": "Rămâne totuși o ipoteză care merită privită cu prudență.",
    "deepseek": "Datele confirmă această concluzie.",
}
_HUMAN_ANSWERS: dict[str, tuple[str, str, str]] = {
    "personal": (
        "Despre „{topic}”, sincer cred că depinde de ce contează pentru tine. "
        "Eu m-aș uita întâi la avantajele și dezavantajele fiecărei variante.",
        "La „{topic}”, eu m-aș uita la mai multe puncte de vedere. "
        "Un exemplu concret ar ajuta să vedem ce se potrivește mai bine.",
        "Cu „{topic}”, nu cred că există un răspuns bun pentru toată lumea. "
        "Contează mult situația și ce vrei să obții.",
    ),
    "definition": (
        "{topic} e un concept care ne ajută să descriem un fenomen. "
        "De obicei, un exemplu simplu face sensul mult mai clar.",
        "De obicei, {topic} înseamnă felul în care înțelegem un anumit lucru. "
        "Sensul exact poate să difere puțin în funcție de context.",
        "Eu aș explica {topic} cât mai simplu: e un concept cu câteva "
        "caracteristici clare. Dacă vrei, putem lua și un exemplu concret.",
    ),
    "why": (
        "Când vine vorba de {topic}, de obicei nu există o singură cauză. "
        "Contează și condițiile din jur, nu doar un singur factor.",
        "Explicația pentru {topic} ține de mai multe lucruri care se leagă între ele. "
        "Dacă ne uităm la un exemplu, devine mai ușor de înțeles.",
        "De obicei, există mai mulți factori care influențează {topic}. "
        "Uneori, un detaliu mic poate schimba destul de mult rezultatul.",
    ),
    "how": (
        "Ca să înțelegi {topic}, începe prin a urmări ce se întâmplă în fiecare "
        "etapă. Apoi leagă pașii între ei; de obicei acolo se vede mecanismul.",
        "Ia {topic} pas cu pas, fără să sari direct la concluzie. "
        "Un exemplu simplu te ajută să vezi cum se leagă lucrurile.",
        "Începe cu ideea de bază despre {topic}, apoi verifică fiecare pas. "
        "Dacă ceva nu se potrivește, merită să te întorci și să vezi de ce.",
    ),
    "quantity": (
        "Cât e {topic} depinde de unitatea și situația despre care vorbim. "
        "Dacă-mi spui ce anume măsurăm, pot să-ți dau o estimare mai bună.",
        "Pentru {topic}, aș verifica întâi unitățile și datele pe care le avem. "
        "Altfel riscăm să dăm un număr care nu prea spune nimic.",
        "Greu de dat o valoare exactă pentru {topic} fără puțin context. "
        "Dar putem face o estimare dacă știm ce vrem să măsurăm.",
    ),
    "comparison": (
        "Când compari {topic}, uită-te la ce contează cel mai mult pentru tine. "
        "Una poate fi mai potrivită decât cealaltă, în funcție de situație.",
        "Nu cred că există o variantă mai bună pentru toată lumea la {topic}. "
        "Aș compara întâi avantajele și apoi aș vedea ce se potrivește scopului.",
        "La {topic}, alegerea depinde mult de criteriul pe care îl folosești. "
        "Dacă-mi spui ce urmărești, putem compara opțiunile mai concret.",
    ),
    "yes_no": (
        "Aș zice că depinde de context, deci nu m-aș grăbi cu un da sau nu. "
        "Dacă-mi spui puțin mai mult, îți pot răspunde mai sigur.",
        "Pe scurt, răspunsul poate fi da într-o situație și nu în alta. "
        "Contează ce condiții avem în cazul ăsta.",
        "Sincer, nu cred că se poate răspunde doar cu da sau nu fără detalii. "
        "Spune-mi un pic mai mult și vedem împreună.",
    ),
    "other": (
        "Bună întrebare. Ca să-ți răspund cum trebuie, m-ar ajuta să știu "
        "puțin mai exact ce te interesează despre {topic}.",
        "Hmm, despre {topic} sunt câteva lucruri pe care le putem lămuri. "
        "Ce parte te interesează cel mai mult?",
        "Pot să încerc, dar am nevoie de un pic de context despre {topic}. "
        "Așa îți dau un răspuns mai la obiect.",
    ),
}
_HUMAN_VOICES = {
    "chatgpt": "Uite,",
    "gemini": "Uite ce interesant:",
    "copilot": "Practic,",
    "grok": "Sincer,",
    "claude": "Din câte văd,",
    "deepseek": "Pe scurt,",
}


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )


def classify_question(question: str) -> tuple[str, str]:
    """Return a Romanian question category and its trailing topic."""
    question = question.strip()
    normalized = _normalize(question)
    matches: list[tuple[int, int, str, int]] = []
    for category, phrase_groups in _KEYWORDS.items():
        for group in phrase_groups:
            for phrase in group:
                phrase_pattern = r"\s+".join(
                    re.escape(part) for part in phrase.split()
                )
                match = re.search(
                    rf"(?<!\w){phrase_pattern}(?!\w)", normalized
                )
                if match:
                    matches.append(
                        (match.start(), -len(phrase), category, match.end())
                    )
    if not matches:
        return "other", _clean_topic(question)

    _, _, category, matched_end = min(matches)
    comparison_match = re.search(
        r"(?<!\w)(?:sau|mai\s+bun|mai\s+bine|compara)(?!\w)",
        normalized,
    )
    if comparison_match:
        category = "comparison"
    topic = question[matched_end:].strip(" \t\r\n:,-")
    return category, _clean_topic(topic)


def _clean_topic(topic: str) -> str:
    cleaned = topic.strip().rstrip(" ?!.,;:")
    cleaned = re.sub(r"^(?:este|sunt|era|ar fi)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned or "subiectul"


def _sentence_count(text: str) -> int:
    """Count sentence-ending punctuation while ignoring punctuation in numbers."""
    return len(re.findall(r"[.!?](?:\s|$)", text))


def _answer_topic(question: str, category: str, topic: str) -> str:
    """Turn the extracted question tail into a phrase that reads naturally in an answer."""
    topic = re.sub(r"^(?:despre|privind)\s+", "", topic, flags=re.IGNORECASE)
    if category == "comparison":
        compared = re.search(
            r"(.+?)\s+(?:sau|ori|versus)\s+(.+?)[?!.]*$",
            question.strip(),
            flags=re.IGNORECASE,
        )
        if compared:
            left = re.sub(
                r"^(?:(?:este|e|sunt|care e|ce e)\s+)+",
                "",
                compared.group(1).strip(),
                flags=re.IGNORECASE,
            )
            left = re.sub(
                r"\s+(?:(?:e|este|sunt)\s+)?(?:mai\s+)?"
                r"(?:bun[ăa]?|bun[ieă]|util[ăa]?|rapid[ăa]?|ieftin[ăa]?|"
                r"interesant[ăa]?|important[ăa]?)$",
                "",
                left,
                flags=re.IGNORECASE,
            )
            return f"{left[0].lower() + left[1:]} și {compared.group(2).strip()}"

    if category == "why" and _normalize(topic).startswith("ploua"):
        return "ploaie"

    prefixes = (
        r"spune-mi\s+(?:despre\s+)?",
        r"explică\s+(?:despre\s+)?",
        r"explica\s+(?:despre\s+)?",
        r"povestește-mi\s+(?:despre\s+)?",
        r"povesteste-mi\s+(?:despre\s+)?",
        r"funcționează\s+",
        r"functioneaza\s+",
        r"învățăm\s+(?:despre\s+)?",
        r"invatam\s+(?:despre\s+)?",
        r"folosim\s+",
        r"ajută\s+",
        r"ajuta\s+",
        r"contează\s+",
        r"conteaza\s+",
        r"se întâmplă\s+",
        r"se intampla\s+",
        r"se face\s+",
        r"bem\s+",
        r"e\s+",
        r"este\s+",
        r"costă\s+",
        r"costa\s+",
        r"înseamnă\s+",
        r"inseamna\s+",
    )
    for prefix in prefixes:
        topic = re.sub(rf"^{prefix}", "", topic, count=1, flags=re.IGNORECASE)
    topic = re.sub(
        r"\s+(?:bem|folosim|consumăm|consumam|măsurăm|masuram)$",
        "",
        topic,
        flags=re.IGNORECASE,
    )
    if not topic:
        return "ploaia" if category == "why" else "subiectul"
    return topic


class MockProvider(AnswerProvider):
    """Generate varied Romanian demo answers without network access."""

    def __init__(
        self,
        seed: int | None = None,
        min_delay: float = 1.0,
        max_delay: float = 4.0,
        wrong_answer_probability: float = 0.15,
    ) -> None:
        """Configure deterministic randomness, response delay, and misleading rate."""
        if seed is not None and (
            not isinstance(seed, int) or isinstance(seed, bool)
        ):
            raise TypeError("seed must be an integer or None")
        for name, value in (("min_delay", min_delay), ("max_delay", max_delay)):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"{name} must be a finite number")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if min_delay > max_delay:
            raise ValueError("min_delay must be less than or equal to max_delay")
        if not isinstance(wrong_answer_probability, (int, float)) or isinstance(
            wrong_answer_probability, bool
        ):
            raise TypeError("wrong_answer_probability must be a finite number")
        if not math.isfinite(wrong_answer_probability):
            raise ValueError("wrong_answer_probability must be a finite number")
        if not 0 <= wrong_answer_probability <= 1:
            raise ValueError("wrong_answer_probability must be between 0 and 1")
        self._random = random.Random(seed)
        self._min_delay = float(min_delay)
        self._max_delay = float(max_delay)
        self._wrong_answer_probability = float(wrong_answer_probability)

    @property
    def name(self) -> str:
        """Stable identifier consumed by the GUI's DEMO marker."""
        return "mock"

    def get_answer(self, question: str, agent: Agent) -> str:
        """Return a personality- and question-aware Romanian answer."""
        if not isinstance(question, str):
            raise TypeError("question must be a string")
        if not question.strip():
            raise ValueError("question must not be empty")
        if not isinstance(agent, Agent):
            raise TypeError("agent must be an Agent")
        if self._max_delay:
            delay = self._random.uniform(self._min_delay, self._max_delay)
            if delay:
                time.sleep(delay)

        category, extracted_topic = classify_question(question)
        topic = _answer_topic(question, category, extracted_topic)
        personality = agent.id.casefold()
        templates = _TEMPLATES[category].get(
            personality, _TEMPLATES[category]["chatgpt"]
        )
        template_index = self._random.randrange(len(templates))
        good_template, wrong_template = templates[template_index]
        misleading = self._random.random() < self._wrong_answer_probability
        template = wrong_template if misleading else good_template
        answer = template.format(topic=topic)
        if not misleading and category in _HUMAN_ANSWERS:
            natural_templates = _HUMAN_ANSWERS[category]
            answer = natural_templates[
                template_index % len(natural_templates)
            ].format(topic=topic)
            if category != "personal":
                voice = _HUMAN_VOICES.get(personality, _HUMAN_VOICES["chatgpt"])
                answer = f"{voice} {answer[0].lower() + answer[1:]}"
        if misleading and _sentence_count(answer) == 1:
            closer = _MISLEADING_CLOSERS.get(
                personality, _MISLEADING_CLOSERS["chatgpt"]
            )
            answer = f"{answer} {closer}"
        return answer
