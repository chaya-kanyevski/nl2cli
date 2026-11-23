# סביבת ארגז-חול לאימות פקודות שה-agent מייצר.
# נבנית אוטומטית בהרצה הראשונה, או ידנית:  docker build -t nl2cli-sandbox sandbox/
FROM ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      procps iproute2 net-tools iputils-ping findutils coreutils grep sed gawk \
      tree file lsb-release ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash sandbox
WORKDIR /home/sandbox

# קבצי דמה כדי שלפקודות יהיה על מה לעבוד
RUN mkdir -p downloads Downloads documents archive old projects/app \
 && touch downloads/a.tmp downloads/b.tmp downloads/keep.txt \
 && printf "line1\nline2\nline3\n" > notes.txt \
 && printf "INFO start\nERROR disk full\nINFO retry\nerror timeout\n" > app.log \
 && printf "id,name\n1,a\n2,b\n3,c\n" > data.csv \
 && printf "x" > old.txt \
 && touch report.docx summary.docx manual.pdf invoice.pdf readme.txt projects/app/main.txt \
 && head -c 5000000 /dev/zero > big.bin \
 && head -c 200000 /dev/zero > medium.bin \
 && chown -R sandbox:sandbox /home/sandbox

USER sandbox
CMD ["bash"]
