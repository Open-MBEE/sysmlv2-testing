package svt;

import org.omg.sysml.interactive.SysMLInteractive;
import org.omg.sysml.interactive.SysMLInteractiveResult;
import org.eclipse.xtext.validation.Issue;
import org.omg.sysml.lang.sysml.Element;
import org.omg.sysml.lang.sysml.Feature;
import org.omg.sysml.lang.sysml.Membership;
import org.omg.sysml.lang.sysml.Redefinition;
import org.omg.sysml.lang.sysml.Type;

import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * Tiny headless glue over the Pilot Implementation's SysMLInteractive engine
 * (org.omg.sysml.interactive) -- no Eclipse Workbench, no Jupyter protocol.
 *
 * Usage: java -jar pilot-glue.jar <file1.sysml> [file2.sysml ...]
 * Env:   SYSML_LIBRARY_DIR - path to a sysml.library directory (the Pilot
 *        repo's own sysml.library/, or an equivalent OMG standard library
 *        checkout). Required for any input that imports the standard
 *        library (ScalarValues, Connections, etc).
 *
 * All files are concatenated into a single compilation unit and processed
 * in one SysMLInteractive.process(content, true) call -- matching how the
 * opensysml adapter feeds a multi-file TestCase to OpenSysML (one
 * concatenated content string), so a "does this multi-file model check
 * clean" comparison means the same thing across adapters. (An earlier
 * version processed each file as its own indexed resource in sequence;
 * confirmed both ways give the same verdict on every seeded test case, so
 * this is a consistency/simplicity choice, not a bug fix -- in particular,
 * the Pilot Implementation's "Must have at least two related elements"
 * error on end-feature-redefinition-explicit is the Pilot's own behavior
 * either way, not a harness artifact.)
 *
 * Two modes:
 *
 *   java -jar pilot-glue.jar <file1.sysml> [file2.sysml ...]
 *     Prints "CLEAN" and exits 0 if there is no error-severity issue;
 *     otherwise prints every issue and exits 1. (structural-check)
 *
 *   java -jar pilot-glue.jar --redef <containerQualifiedName> <file1.sysml> [file2.sysml ...]
 *     For reference-resolution: enumerates <containerQualifiedName>'s own
 *     ownedMembership list (declaration order), finds each owned Feature
 *     with an explicit Redefinition, and prints one line per redefinition,
 *     "<containerQualifiedName>::@<i>\t<resolvedTargetLocator>" (i in
 *     declaration order) -- real EMF object identity via
 *     Redefinition.getRedefinedFeature(), never diagnostics. The target
 *     locator is its qualifiedName when resolvable, else Element.path()
 *     (anonymous/shadowed siblings have no resolvable qualifiedName --
 *     see Element.getQualifiedName()'s own doc).
 *
 * Both modes' plain text is captured verbatim by
 * adapters/pilot_implementation.py as the RawResult -- kept free of
 * loadLibrary's own "Reading .../*.sysml..." log lines (suppressed below)
 * so the precise output is the actual result, not library-loading noise.
 */
public class Main {
    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            System.err.println(
                "usage: java -jar pilot-glue.jar <file1.sysml> [file2.sysml ...]\n"
                + "   or: java -jar pilot-glue.jar --redef <containerQualifiedName> <file1.sysml> [file2.sysml ...]");
            System.exit(2);
        }

        boolean redefMode = args[0].equals("--redef");
        String containerName = redefMode ? args[1] : null;
        String[] fileArgs = redefMode
                ? java.util.Arrays.copyOfRange(args, 2, args.length)
                : args;

        SysMLInteractive instance = SysMLInteractive.createInstance();
        String libraryDir = System.getenv("SYSML_LIBRARY_DIR");
        if (libraryDir != null && !libraryDir.isEmpty()) {
            // loadLibrary prints one "Reading ..." line per stdlib file (of
            // which there are hundreds) directly to System.out -- real
            // signal, but not about this run's test case, so it's
            // suppressed here and restored immediately after.
            PrintStream realOut = System.out;
            System.setOut(new PrintStream(OutputStream.nullOutputStream()));
            try {
                instance.loadLibrary(libraryDir);
            } finally {
                System.setOut(realOut);
            }
        }

        StringBuilder content = new StringBuilder();
        for (String path : fileArgs) {
            content.append(new String(Files.readAllBytes(Paths.get(path))));
            content.append("\n");
        }

        List<String> lines = new ArrayList<>();
        boolean anyErrors;
        SysMLInteractiveResult result = instance.process(content.toString(), true);
        if (result.getException() != null) {
            anyErrors = true;
            lines.add("EXCEPTION: " + result.getException());
        } else {
            anyErrors = result.hasErrors();
            for (Issue issue : result.getIssues()) {
                lines.add(issue.getSeverity() + ": " + issue.getMessage()
                        + " (line " + issue.getLineNumber() + ")");
            }
        }

        if (redefMode && !anyErrors) {
            List<String> redefLines = resolveRedefinitions(instance, containerName);
            for (String line : redefLines) {
                System.out.println(line);
            }
            System.exit(0);
        }

        System.out.println(anyErrors ? "ERRORS:" : "CLEAN");
        for (String line : lines) {
            System.out.println(line);
        }
        System.exit(anyErrors ? 1 : 0);
    }

    private static List<String> resolveRedefinitions(SysMLInteractive instance, String containerName) {
        List<String> out = new ArrayList<>();
        Element containerEl = instance.resolve(containerName);
        if (!(containerEl instanceof Type)) {
            out.add(containerName + "::@0\tUNRESOLVED:not-a-type-or-not-found");
            return out;
        }
        Type container = (Type) containerEl;
        int i = 0;
        for (Membership m : container.getOwnedMembership()) {
            Element member = m.getMemberElement();
            if (!(member instanceof Feature)) {
                continue;
            }
            Feature feature = (Feature) member;
            for (Redefinition r : feature.getOwnedRedefinition()) {
                Feature target = r.getRedefinedFeature();
                String targetName = target.getQualifiedName();
                String label = targetName != null ? targetName : target.path();
                out.add(containerName + "::@" + i + "\t" + label);
                i++;
            }
        }
        return out;
    }
}
