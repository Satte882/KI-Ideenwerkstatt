# ADR 0001: Modularer Django-Monolith

## Status
Akzeptiert

## Kontext
KI-Radar ist eine kleine formular- und workfloworientierte interne Anwendung. Eine API-first-Architektur mit separatem Frontend würde zusätzliche Authentifizierungs-, Berechtigungs- und Deploymentkomplexität erzeugen.

## Entscheidung
Django 5.2 LTS, serverseitige Templates und PostgreSQL werden als einzelnes deploybares System verwendet.

## Konsequenzen
Django Admin, Authentifizierung und ORM können direkt genutzt werden. Eine spätere API bleibt möglich, ist aber nicht Bestandteil der ersten Version.
