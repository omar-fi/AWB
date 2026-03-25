package com.digitalbank.predictbackend.service;

import com.digitalbank.predictbackend.entities.PredictionVisite;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;

import java.time.format.DateTimeFormatter;
import java.util.Locale;

@Service
public class EmailService {

    private final JavaMailSender mailSender;
    private static final DateTimeFormatter DATE_FR = DateTimeFormatter.ofPattern("EEEE d MMMM yyyy", Locale.FRENCH);

    public EmailService(JavaMailSender mailSender) {
        this.mailSender = mailSender;
    }

    // ── Email de bienvenue (à la création du client) ─────────────────────────
    public void envoyerEmailBienvenue(String emailDestinataire, String nomClient) {
        try {
            System.out.println("📧 Envoi email bienvenue → " + emailDestinataire);

            SimpleMailMessage message = new SimpleMailMessage();
            message.setFrom("filaliomar070@gmail.com");
            message.setTo(emailDestinataire);
            message.setSubject("Bienvenue chez AWB — votre banque vous ouvre ses portes !");

            String contenu = "Bonjour " + nomClient + ",\n\n"
                    + "✨ Nous sommes ravis de vous accueillir dans la famille AWB !\n\n"
                    + "Votre compte a été créé avec succès par votre conseiller dédié.\n"
                    + "Vous pouvez dès maintenant profiter de l'ensemble de nos services\n"
                    + "et bénéficier d'un accompagnement personnalisé à chaque étape.\n\n"
                    + "N'hésitez pas à contacter votre agence pour toute question.\n\n"
                    + "À très bientôt,\n"
                    + "L'équipe AWB Digital Banking 🏦";

            message.setText(contenu);
            mailSender.send(message);
            System.out.println("✅ Email bienvenue envoyé → " + emailDestinataire);
        } catch (Exception e) {
            System.err.println("❌ Erreur email bienvenue : " + e.getMessage());
            e.printStackTrace();
        }
    }

    // ── Email de prédiction personnalisé ────────────────────────────────────
    public void envoyerEmailPrediction(String emailDestinataire, String nomClient,
                                       PredictionVisite prediction) {
        if (emailDestinataire == null || emailDestinataire.isBlank()) return;
        try {
            System.out.println("📧 Envoi email prédiction → " + emailDestinataire);

            String operation   = prediction.getOperationPrevue()      != null ? prediction.getOperationPrevue()      : "une opération bancaire";
            String plage       = prediction.getPlageHorairePrevue()   != null ? prediction.getPlageHorairePrevue()   : "dans la journée";
            String datePrevue  = prediction.getDatePrevue()           != null ? prediction.getDatePrevue().format(DATE_FR) : "prochainement";
            Double score       = prediction.getScoreProbabiliteGlobal();
            String insight     = prediction.getInsightGenai();

            // Icône et ton selon le score de confiance
            String scoreLabel, ouverture, conseil;
            if (score != null && score >= 0.75) {
                scoreLabel = "🔥 Très probable";
                ouverture  = "Notre intelligence artificielle est très confiante :";
                conseil    = "Préparez vos documents à l'avance pour gagner du temps lors de votre passage en agence.";
            } else if (score != null && score >= 0.50) {
                scoreLabel = "📊 Probable";
                ouverture  = "Selon notre analyse, il est probable que :";
                conseil    = "N'hésitez pas à prendre rendez-vous en ligne pour être accueilli(e) dans les meilleures conditions.";
            } else {
                scoreLabel = "🔮 À surveiller";
                ouverture  = "Notre système a détecté un signal intéressant pour vous :";
                conseil    = "Contactez votre conseiller si vous avez des questions sur vos services bancaires.";
            }

            String sujet = "AWB — Votre agenda bancaire du " + datePrevue;

            StringBuilder corps = new StringBuilder();
            corps.append("Bonjour ").append(nomClient).append(",\n\n");
            corps.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
            corps.append("   VOTRE PRÉVISION PERSONNALISÉE\n");
            corps.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n");
            corps.append(ouverture).append("\n\n");
            corps.append("  📅 Date probable de visite : ").append(datePrevue).append("\n");
            corps.append("  🕐 Plage horaire idéale    : ").append(plage).append("\n");
            corps.append("  🏦 Opération anticipée     : ").append(operation).append("\n");
            corps.append("  ").append(scoreLabel).append(
                    score != null ? String.format(" (%.0f%% de confiance)", score * 100) : "").append("\n\n");

            if (insight != null && !insight.isBlank()) {
                corps.append("💡 Analyse IA :\n");
                corps.append(insight).append("\n\n");
            }

            corps.append("───────────────────────────────\n");
            corps.append("📌 Notre conseil pour vous :\n");
            corps.append(conseil).append("\n\n");
            corps.append("Merci de votre confiance et à bientôt dans votre agence AWB.\n\n");
            corps.append("Cordialement,\n");
            corps.append("L'équipe AWB Digital Banking 🏦\n");
            corps.append("(Cet email a été généré automatiquement par notre système IA — ne pas répondre directement.)");

            SimpleMailMessage message = new SimpleMailMessage();
            message.setFrom("filaliomar070@gmail.com");
            message.setTo(emailDestinataire);
            message.setSubject(sujet);
            message.setText(corps.toString());
            mailSender.send(message);

            System.out.println("✅ Email prédiction envoyé → " + emailDestinataire);
        } catch (Exception e) {
            System.err.println("❌ Erreur email prédiction : " + e.getMessage());
            e.printStackTrace();
        }
    }
}