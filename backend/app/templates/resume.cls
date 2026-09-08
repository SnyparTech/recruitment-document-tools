%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Medium Length Professional CV - RESUME CLASS FILE
%
% This class file defines the structure and design of the template. 
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

\ProvidesClass{resume}[2010/07/10 v0.9 Resume class]

\LoadClass[10pt,letterpaper]{article} % Font size and paper type

\usepackage[parfill]{parskip} % Remove paragraph indentation
\usepackage{array} % Required for boldface tabular columns
\usepackage{ifthen} % Required for ifthenelse statements

\pagestyle{empty} % Suppress page numbers

%----------------------------------------------------------------------------------------
%	HEADINGS COMMANDS: Commands for printing name and address
%----------------------------------------------------------------------------------------

\def \name#1{\def\@name{#1}} % Defines the \name command to set name
\def \@name {} % Sets \@name to empty by default

\def \addressSep {$\diamond$} % Set default address separator to a diamond

% One, two or three address lines can be specified 
\let \@addressone \relax
\let \@addresstwo \relax
\let \@addressthree \relax

% \address command can be used to set the first, second, and third address (in order)
\def \address #1{
  \@ifundefined{@addressone}{
    \def \@addressone {#1}
  }{
    \@ifundefined{@addresstwo}{
      \def \@addresstwo {#1}
    }{
      \def \@addressthree {#1}
    }
  }
}

% \printaddress is used to style an address line (centered and separator between items)
\def \printaddress #1{
  \begingroup
    \def \\ {\addressSep\ }
    \centerline{#1}
  \endgroup
  \par
  \smallskip
}

% \printname is used to print the name in large size and bold
\def \printname {
  \begingroup
    \hfil{\MakeUppercase{\namesize\bf \@name}}\hfil
    \nameskip\break
  \endgroup
}

%----------------------------------------------------------------------------------------
%	PRINT THE HEADING LINES
%----------------------------------------------------------------------------------------

\let\ori@document=\document
\renewcommand{\document}{
  \ori@document  % Begin document
  \printname % Print the name specified with \name
  \@ifundefined{@addressone}{}{ % Print first address if specified
    \printaddress{\@addressone}}
  \@ifundefined{@addresstwo}{}{ % Print second address if specified
    \printaddress{\@addresstwo}}
     \@ifundefined{@addressthree}{}{ % Print third address if specified
    \printaddress{\@addressthree}}
}

%----------------------------------------------------------------------------------------
%	SECTION FORMATTING
%----------------------------------------------------------------------------------------

% Defines the rSection environment for the large sections within the CV
\newenvironment{rSection}[1]{ % 1 input argument - section name
  \sectionskip
  \MakeUppercase{\bf #1} % Section title
  \sectionlineskip
  \hrule % Horizontal line
  \begin{list}{}{ % List for each individual item in the section
    \setlength{\leftmargin}{0em} % Margin within the section
  }
  \item[]
}{
  \end{list}
}

% Defines the rSubsection environment for sub-entries within sections
\newenvironment{rSubsection}[4]{ % 4 input arguments - company, dates, role, location
 {\bf #1} \hfill {#2} % Bold company name and right-aligned dates
 \ifthenelse{\equal{#3}{}}{}{ % If the third argument is not empty, print it
  \\
  {\em #3} \hfill {\em #4} % Italic role and location
  }\smallskip
  \begin{itemize}
   \renewcommand{\labelitemi}{\tiny$\bullet$}
   \setlength{\itemsep}{-0.5em} \vspace{-0.5em} % Tight bullet points
}{
  \end{itemize}
}

% The below commands define the whitespace after certain elements in the resume
\def\namesize{\huge} % Size of the name at the top of the document
\def\addressskip{\smallskip} % The space between the two address (or phone/email) lines
\def\sectionlineskip{\medskip} % The space above the horizontal rule for each section 
\def\nameskip{\bigskip} % The space after your name at the top
\def\sectionskip{\medskip} % The space after the heading section
