#include <QCoreApplication>
#include <QCommandLineParser>
#include <QCommandLineOption>
#include <QFile>
#include <QTextStream>
#include <QString>
#include <QSet>
#include <QFileInfo>
#include <QRegularExpression>
#include <QRandomGenerator>

enum State {
  LOOKING_FOR_START,
  IN_SENTENCE
};

constexpr int MIN_CHARS = 10;
constexpr int MAX_CHARS = 175;

// Check if uppercase Danish letter
bool isUpperDanish(QChar c) {
  return (c >= 'A' && c <= 'Z') || c == u'Æ' || c == u'Ø' || c == u'Å';
}

// Check if lowercase Danish letter
bool isLowerDanish(QChar c) {
  return (c >= 'a' && c <= 'z') || c == u'æ' || c == u'ø' || c == u'å';
}

// Check if valid sentence start (capital followed by another letter)
bool isValidSentenceStart(const QString &line, int i) {
  if (i + 1 >= line.size()) return false;
  return isUpperDanish(line[i]) && line[i+1].isLetter();
}

// Check if substring is abbreviation
bool isAbbreviation(const QString &word) {
  static QSet<QString> abbr = {
    "bl.a",
    "bla",
    "osv",
    "m.fl",
    "mfl",
    "fx",
    "f.x",
    "f.eks",
    "ca",
    "dvs", 
    "d.v.s",
    "evt",
    "jf",
    "jvf",
    "ift",
    "pga",
    "vedr",
    "inkl",
    "incl",
    "ekskl",
    "hhv",
    "stk",
    "nr",
    "no",
    "pkt",
    "fig",
    "tab",
    "kl",
    "min",
    "sek",
    "t",
    "etc",
    "i.e",
    "e.g",
    "f",
    "flg",
    "fk",
    "n",
    "cv",
    "bl",
    "skt",
    "aarh",
    "m",
    "e",
    "ndr",
    "pr",
    "kr",
    "f.kr",
    "d",
    "vs",
    "st",
    "moh",
    "jr",
    "aka",
    "cand",
    "sct",
    "cm",
    "km",
    "mm",
    "eng",
    "h",
    "rd",
    "l",
    "td",
    "ff",
    "j",
    "c",
    "dr",
    "pt",
    "s",
    "al",
    "e.kr",
    "k",
    "a",
    "feat",
    "m.v",
    "mv",
    "c.v",
    "udg",
    "w",
    "b",
    "fork",
    "kg",
    "g",
    "mdr",
    "jan",
    "feb",
    "febr",
    "mar",
    "apr",
    "aug",
    "sep",
    "sept",
    "okt",
    "nov",
    "dec",
    "mht",
    "prof",
    "kvm",
    "iflg",
    "spec",
    "str",
    "co",
    "ml",
    "tlf",
    "mr",
    "hr",
    "j.c",
    "i",
    "pct",
    "e-nr",
    "mio",
    "mia",
    "f.v",
    "f.v.t",
    "n.f",
    "j.p",
    "i.p",
    "cand.it",
    "vol",
    "m.o",
    "p",
    "r",
    "phil",
    "cand.phil",
    "kbh",
    "fr",
    "th",
    "tv",
    "c.f",
    "pp",
    "h.a",
    "ltd",
    "v",
    "o",
    "inc",
    "etnogr",
    "sv",
    "nv",
    "sø",
    "nø",
    "gl",
    "q",
    "li",
    "bkg",
    "dr.med",
    "selvf",
    "bp",
    "f.c"
  };
  return abbr.contains(word.toLower().replace("\"", ""));
}

// Determine if punctuation is real sentence end
bool isRealSentenceEnd(const QString &buffer) {
  int pos = buffer.length() - 1;
  if((buffer.count("\"") % 2) != 0) {
    return false;
  }
  if((buffer.count("'") % 2) != 0) {
    return false;
  }
  if(buffer.count("(") == 1 && buffer.count(")") != 1) {
    return false;
  }
  
  if(buffer[pos] == '!' || buffer[pos] == '?')
    return true;

  if(buffer[pos] == '.') {
    // Look backwards to previous space
    int i = pos - 1;
    QString word;

    while(i >= 0 && buffer[i] != ' ' && buffer[i] != '(' && buffer[i] != '"') {
      word.prepend(buffer[i]);
      i--;
    }

    // Rule 1: Number like "4."
    if(!word.isEmpty() && word.back().isDigit())
      return false;

    // Rule 2: Abbreviation
    if(isAbbreviation(word))
      return false;

    return true;
  }

  return false;
}

QString cleanString(QString string)
{
  // Turn double-double-quotes into double-quotes
  string = string.simplified();
  string.replace("»", "\"");
  string.replace("«", "\"");
  string.replace("”", "\"");
  string.replace("“", "\"");
  string.replace("\"\"", "\"");
  string.replace("\"'''", "'");
  string.replace("\"''", "'");
  string.replace("''\"", "'");
  string.replace("\"''", "'");
  string.replace("''''", "'");
  string.replace("'''", "'");
  string.replace("''", "'");
  string.replace("[[", "");
  string.replace("]]", "");
  string.replace("[", "");
  string.replace("]", "");
  string.replace(" .", ".");
  string.replace(" ?", "?");
  string.replace(" !", "!");
  string.replace(",?", "?");
  string.replace("&nbsp;", " ");
  string.replace("&amp;", "&");
  string.replace("TALER", "taler");
  
  return string;
}

bool hasIllegalChars(QString string)
{
  string = string.toLower();
  QRegularExpression re("[^a-zæøåéöüA-ZÆØÅÉÖÜ\\s\\d.,!?'\"():;\\-]");
  QRegularExpression rets("^[A-ZÆØÅa-zæøå0-9 ]{3,16}:"); // Rammer alle af "Figur 3:", "Taler 2:"
  QRegularExpression stk("^[A-ZÆØÅa-zæøå]{1,5}[.]{1}"); // "Stk." og lignende i starten af en sætning
  if(re.match(string).hasMatch() ||
     rets.match(string).hasMatch() ||
     stk.match(string).hasMatch() ||
     string.contains("http") ||
     string.contains("https") ||
     string.contains("....") ||
     string.contains("fil:") ||
     string.contains("file:") ||
     string.contains("kilden:") ||
     string.contains("kategori:") ||
     string.contains("skabelon:") ||
     string.contains("linje ")
     ) {
    return true;
  }
  return false;
}

bool addLines(const QString &regexp, const int &required, QList<QString> &input, QList<QString> &accepted)
{
  QRegularExpression re(regexp);

  printf("Cherrypicking %d lines using regexp '%s', please wait...\n", required, qPrintable(regexp));
  int found = 0;
  while(found < required) {
    if(input.isEmpty())
      return false;

    qint64 selected = QRandomGenerator::global()->bounded(input.length());

    if(re.match(input[selected]).hasMatch()) {
      accepted.append(input[selected]);
      input.remove(selected);
      found++;
    }
  }
  return true;
}

int main(int argc, char *argv[]) {
  QCoreApplication app(argc, argv);

  QCommandLineParser parser;
  parser.addHelpOption();
  parser.addPositionalArgument("input", "Input file to process.");
  QCommandLineOption generateOption("generate", "Activate generator mode");
  parser.addOption(generateOption);
  parser.process(app);

  if(parser.positionalArguments().size() != 1) {
    printf("Missing input file, quitting...\n");
    return 1;
  }

  bool generate = parser.isSet(generateOption);
  if(generate) {
    printf("Generate mode is activated!\n");
  }
  
  QFileInfo inputInfo(parser.positionalArguments().at(0));
  QString input = inputInfo.absoluteFilePath();
  QString output = "output-" + inputInfo.baseName() + ".csv";
  
  QFile inputFile(input);
  QFile outputFile(output);

  if(!inputFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
    qWarning("Could not open '%s'", qPrintable(input));
    return 1;
  }

  if(!outputFile.open(QIODevice::WriteOnly | QIODevice::Text)) {
    qWarning("Could not open '%s'", qPrintable(output));
    return 1;
  }

  QTextStream in(&inputFile);
  QTextStream out(&outputFile);

  if(!generate) {
    printf("Parsing input and looking for sentences...\n");
    State state = LOOKING_FOR_START;
    QString buffer;

    while(!in.atEnd()) {
      QString line = in.readLine();
      line = cleanString(line);

      for(int i = 0; i < line.size(); ++i) {
	QChar c = line[i];

	switch(state) {
	case LOOKING_FOR_START:
	  if(isValidSentenceStart(line, i)) {
	    buffer.clear();
	    buffer += c;
	    state = IN_SENTENCE;
	  }
	  break;

	case IN_SENTENCE:
	  buffer += c;
	  // When we wrapped from a previous line due to missing end-of-line char but the new line is a new sentence! DISCARD!
	  if(i == 0 && isValidSentenceStart(line, i)) {
	    i--;
	    buffer.clear();
	    state = LOOKING_FOR_START;
	    continue;
	  }

	  if(c == '.' || c == '!' || c == '?') {
	    if(isRealSentenceEnd(buffer)) {
	      if(buffer.length() >= MIN_CHARS && buffer.length() <= MAX_CHARS && buffer.count(" ") >= 2) {
		if(!hasIllegalChars(buffer)) {
		  out << buffer << "\n";
		}
		state = LOOKING_FOR_START;
		buffer.clear();
	      }
	    }
	  } else {
	   // Check for end of line and if so clear buffer and start over
	    if(i == line.size() - 1) {
	      state = LOOKING_FOR_START;
	      buffer.clear();
	    }
	   }
	  break;
	}
      }
    }
  } else {
    printf("Generating sentence dataset from input...\n");
    QList<QString> sentences;
    while(!in.atEnd()) {
      sentences.append(in.readLine().simplified());
    }
    printf("Read %llu sentences from input file!\n", sentences.length());

    QList<QString> accepted;

    //addLines("[ ]{1}[0-9]{1,2}[./-]{1}[0-9]{1,2}[./-]{1}[0-9]{2,4}[ ]{1}", 50, sentences, accepted);
    addLines("[!]{1}$", 250, sentences, accepted);
    addLines("[?]{1}$", 250, sentences, accepted);
    addLines("\\d", 500, sentences, accepted);
    addLines("^\\D*$", 2000, sentences, accepted);
    
    for(const auto &line: accepted) {
      out << line << Qt::endl;
    }
  }

  inputFile.close();
  outputFile.close();
  
  return 0;
}
